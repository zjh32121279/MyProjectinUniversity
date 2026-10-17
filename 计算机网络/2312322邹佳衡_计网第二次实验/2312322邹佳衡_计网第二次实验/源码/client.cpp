#include "../RDT.h"
#include <iostream>
#include <vector>
#include <random>
#include <algorithm>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <fstream>
#include <chrono>

using namespace std::chrono;
using namespace std;

#define min(a,b) (((a) < (b)) ? (a) : (b))

struct Packet {
    RDTHeader hdr;
    vector<char> data;
    steady_clock::time_point sent_time;
    bool acked = false;
};

// 添加：客户端关闭状态
enum CloseState {
    CLOSE_IDLE,          // 未开始关闭
    CLOSE_FIN_SENT,      // 已发送FIN，等待ACK
    CLOSE_FIN_ACKED,     // FIN已被ACK，等待服务端FIN
    CLOSE_WAIT_FIN_ACK   // 已收到服务端FIN并发送ACK，等待结束
};

CloseState close_state = CLOSE_IDLE;
bool received_server_fin = false;
uint32_t server_fin_seq = 0;

// parameters (can be tuned)
int SENDER_MSS = 1000;
int MAX_WINDOW = 32;
int RTO_MS = 200;
double LOSS_PROB = 0.0;

// Client's advertised receive window (now uses MAX_WINDOW from command line)
int CLIENT_ADVERTISED_WINDOW = 32;  // Will be updated from command line

// networking
SOCKET sockfd = INVALID_SOCKET;
SOCKADDR_IN servaddr;

// sender state
mutex mtx;
condition_variable cv;
vector<Packet> packets;
uint32_t send_base = 0;
uint32_t next_seq = 0;
int cwnd = 1;
int ssthresh = 16;
int dupAckCount = 0;
uint32_t lastAck = 0;
int receiver_wnd = MAX_WINDOW; // from receiver's ACK (server's receive window)
uint32_t sack_bitmap = 0;
bool finished = false;
int total_acks_received = 0;

// RNG for loss simulation
static std::mt19937_64 loss_rng((unsigned)std::chrono::steady_clock::now().time_since_epoch().count());
static std::uniform_real_distribution<double> loss_dist(0.0, 1.0);

// helper to send with optional simulated loss
static int send_with_optional_loss(const char* buf, int len, const sockaddr_in* dst) {
    if (LOSS_PROB > 0.0 && loss_dist(loss_rng) < LOSS_PROB) {
        // simulate drop
        return len;
    }
    return sendto(sockfd, buf, len, 0, (const sockaddr*)dst, sizeof(*dst));
}

void recv_thread_func() {
    char buf[sizeof(RDTHeader) + 256];
    while (!finished) {
        sockaddr_in from;
        int fromlen = sizeof(from);
        int r = recvfrom(sockfd, buf, sizeof(buf), 0, (sockaddr*)&from, &fromlen);
        if (r <= 0) {
            this_thread::sleep_for(milliseconds(5));
            continue;
        }

        // verify checksum
        if (!verify_checksum_raw(buf, r)) {
            cout << "[recv] ACK checksum failed" << endl;
            continue;
        }

        RDTHeader hdr;
        memcpy(&hdr, buf, sizeof(RDTHeader));
        hdr_ntoh(&hdr);

        // 新增：处理服务端的FIN
        if (hdr.flags & RDT_FIN) {
            unique_lock<mutex> lk(mtx);
            cout << "[recv] received FIN from server, seq=" << hdr.seq << endl;
            received_server_fin = true;
            server_fin_seq = hdr.seq;
            
            // 发送ACK确认服务端的FIN
            RDTHeader ack_hdr;
            memset(&ack_hdr, 0, sizeof(ack_hdr));
            ack_hdr.seq = next_seq;
            ack_hdr.ack = hdr.seq + 1;
            ack_hdr.flags = RDT_ACK;
            ack_hdr.wnd = CLIENT_ADVERTISED_WINDOW;
            fill_checksum(&ack_hdr, nullptr);
            
            RDTHeader net_ack = ack_hdr;
            hdr_hton(&net_ack);
            sendto(sockfd, (char*)&net_ack, sizeof(net_ack), 0, 
                  (sockaddr*)&servaddr, sizeof(servaddr));
            
            cout << "[fin] sent ACK for server FIN, ack=" << ack_hdr.ack << endl;
            
            close_state = CLOSE_WAIT_FIN_ACK;
            cv.notify_all();
        }

        if (hdr.flags & RDT_ACK) {
            unique_lock<mutex> lk(mtx);
            total_acks_received++;

            // 新增：处理对我们FIN的ACK
            if (close_state == CLOSE_FIN_SENT) {
                // 检查是否有包确认了我们的FIN
                for (auto& p : packets) {
                    if ((p.hdr.flags & RDT_FIN) && !p.acked && 
                        p.hdr.seq + 1 <= hdr.ack) {
                        p.acked = true;
                        cout << "[fin] our FIN acknowledged, waiting for server FIN" << endl;
                        close_state = CLOSE_FIN_ACKED;
                        break;
                    }
                }
            }

            // Debug: print received ACK info every 100 ACKs
            if (total_acks_received % 100 == 0) {
                cout << "[recv_ack#" << total_acks_received << "] ack=" << hdr.ack
                    << " wnd=" << hdr.wnd
                    << " sack=0x" << hex << hdr.sack << dec
                    << " flags=" << hdr.flags << endl;
            }

            uint32_t acknum = hdr.ack;

            // Update receiver window from ACK (server's receive capability)
            if (hdr.wnd > 0) {
                receiver_wnd = hdr.wnd;
            }

            // Update SACK bitmap
            sack_bitmap = hdr.sack;

            // Mark packets with seq < acknum as acked
            for (auto& p : packets) {
                if (!p.acked && p.hdr.seq + p.hdr.len <= acknum) {
                    p.acked = true;
                    if (total_acks_received % 100 == 0) {
                        cout << "[ack] packet seq=" << p.hdr.seq << " cumulatively acked" << endl;
                    }
                }
            }

            // Process SACK bitmap
            if (sack_bitmap > 0) {
                for (int i = 0; i < RDT_MAX_SACK_BITS; ++i) {
                    if (sack_bitmap & (1u << i)) {
                        uint32_t seq = acknum + (uint32_t)i * (uint32_t)SENDER_MSS;
                        for (auto& p : packets) {
                            if (!p.acked && p.hdr.seq == seq) {
                                p.acked = true;
                                if (total_acks_received % 50 == 0) {
                                    cout << "[sack] packet seq=" << p.hdr.seq << " selectively acked" << endl;
                                }
                                break;
                            }
                        }
                    }
                }
            }

            if (acknum > lastAck) {
                dupAckCount = 0;
                lastAck = acknum;
                send_base = acknum;

                // congestion control with limit
                if (cwnd < ssthresh) { // slow-start
                    cwnd += 1;
                    // Limit cwnd growth to avoid exceeding receiver capability
                    if (cwnd > receiver_wnd * 2) {
                        cwnd = receiver_wnd * 2;
                    }
                    if (total_acks_received % 50 == 0) {
                        cout << "[congestion] slow-start: cwnd=" << cwnd << endl;
                    }
                }
                else { // congestion avoidance
                    static int ack_acc = 0;
                    ack_acc++;
                    if (ack_acc >= cwnd) {
                        cwnd++;
                        // Limit cwnd growth
                        if (cwnd > receiver_wnd * 2) {
                            cwnd = receiver_wnd * 2;
                        }
                        ack_acc = 0;
                        if (total_acks_received % 100 == 0) {
                            cout << "[congestion] avoidance: cwnd=" << cwnd << endl;
                        }
                    }
                }
            }
            else if (acknum == lastAck) {
                dupAckCount++;
                if (dupAckCount == 3) {
                    // fast retransmit
                    ssthresh = max(1, cwnd / 2);
                    cwnd = ssthresh + 3;
                    cout << "[congestion] fast retransmit: ssthresh=" << ssthresh << " cwnd=" << cwnd << endl;

                    // retransmit earliest unacked packet
                    for (auto& p : packets) {
                        if (!p.acked) {
                            p.sent_time = steady_clock::now();
                            if (p.hdr.len && !p.data.empty()) {
                                vector<char> out(sizeof(RDTHeader) + p.data.size());
                                RDTHeader th = p.hdr;
                                th.wnd = CLIENT_ADVERTISED_WINDOW; // Use updated client window
                                fill_checksum(&th, p.data.data());
                                hdr_hton(&th);
                                memcpy(out.data(), &th, sizeof(RDTHeader));
                                memcpy(out.data() + sizeof(RDTHeader), p.data.data(), p.data.size());
                                sendto(sockfd, out.data(), (int)out.size(), 0, (sockaddr*)&servaddr, sizeof(servaddr));
                                cout << "[retransmit] fast retransmit seq=" << p.hdr.seq << endl;
                            }
                            break;
                        }
                    }
                }
            }
            cv.notify_all();
        }
    }
}

int perform_handshake() {
    // send SYN
    RDTHeader sh;
    memset(&sh, 0, sizeof(sh));
    sh.seq = 0;
    sh.ack = 0;
    sh.flags = RDT_SYN;
    sh.len = 0;
    sh.wnd = CLIENT_ADVERTISED_WINDOW;  // Client's advertised window
    sh.sack = 0;
    fill_checksum(&sh, nullptr);
    RDTHeader netsh = sh; hdr_hton(&netsh);
    sendto(sockfd, (char*)&netsh, sizeof(netsh), 0, (sockaddr*)&servaddr, sizeof(servaddr));
    cout << "[handshake] sent SYN, wnd=" << sh.wnd << endl;

    // wait for SYN+ACK
    char buf[sizeof(RDTHeader) + 200];
    sockaddr_in from;
    int fromlen = sizeof(from);
    auto start = steady_clock::now();
    while (true) {
        int r = recvfrom(sockfd, buf, sizeof(buf), 0, (sockaddr*)&from, &fromlen);
        if (r > 0) {
            if (!verify_checksum_raw(buf, r)) continue;
            RDTHeader rh; memcpy(&rh, buf, sizeof(RDTHeader)); hdr_ntoh(&rh);
            if ((rh.flags & RDT_SYN) && (rh.flags & RDT_ACK)) {
                cout << "[handshake] received SYN+ACK, server wnd=" << rh.wnd << endl;
                // update receiver window from server
                receiver_wnd = rh.wnd;

                // send ACK
                RDTHeader ah;
                memset(&ah, 0, sizeof(ah));
                ah.seq = 1;
                ah.ack = rh.seq + 1;
                ah.flags = RDT_ACK;
                ah.wnd = CLIENT_ADVERTISED_WINDOW;  // Client's advertised window
                fill_checksum(&ah, nullptr);
                RDTHeader netah = ah; hdr_hton(&netah);
                sendto(sockfd, (char*)&netah, sizeof(netah), 0, (sockaddr*)&servaddr, sizeof(servaddr));
                cout << "[handshake] sent ACK, wnd=" << ah.wnd << endl;
                return 0;
            }
        }
        if (duration_cast<milliseconds>(steady_clock::now() - start).count() > 2000) {
            // retransmit SYN
            sendto(sockfd, (char*)&netsh, sizeof(netsh), 0, (sockaddr*)&servaddr, sizeof(servaddr));
            cout << "[handshake] retransmit SYN" << endl;
            start = steady_clock::now();
        }
    }
}

int main(int argc, char** argv) {
    if (argc < 4) {
        cout << "Usage: RDTClient <server_ip> <server_port> <file_path>\n";
        cout << "Options:\n";
        cout << "  --mss N     : Maximum Segment Size in bytes (default 1000)\n";
        cout << "  --wnd N     : Client advertised window size in segments (default 32)\n";
        cout << "  --rto N     : Retransmission timeout in ms (default 200)\n";
        cout << "  --loss F    : Simulated loss probability 0.0-1.0 (default 0.0)\n";
        return 1;
    }
    const char* svr = argv[1];
    int port = atoi(argv[2]);
    string file = argv[3];

    // parse optional flags
    for (int ai = 4; ai < argc; ++ai) {
        std::string a = argv[ai];
        if (a == "--mss" && ai + 1 < argc) {
            SENDER_MSS = atoi(argv[++ai]);
            if (SENDER_MSS <= 0) SENDER_MSS = 1000;
        }
        else if (a == "--wnd" && ai + 1 < argc) {
            MAX_WINDOW = atoi(argv[++ai]);
            if (MAX_WINDOW <= 0) MAX_WINDOW = 1;
            // Update client advertised window to use command line parameter
            CLIENT_ADVERTISED_WINDOW = MAX_WINDOW;
            receiver_wnd = MAX_WINDOW;
        }
        else if (a == "--rto" && ai + 1 < argc) {
            RTO_MS = atoi(argv[++ai]);
            if (RTO_MS <= 0) RTO_MS = 200;
        }
        else if (a == "--loss" && ai + 1 < argc) {
            LOSS_PROB = atof(argv[++ai]);
            if (LOSS_PROB < 0.0) LOSS_PROB = 0.0;
            if (LOSS_PROB > 1.0) LOSS_PROB = 1.0;
        }
        else if (a == "--help" || a == "-h") {
            cout << "Usage: RDTClient <server_ip> <server_port> <file_path> [--mss N] [--wnd N] [--rto N] [--loss F]\n";
            return 0;
        }
    }

    // init winsock
    WSAData ws;
    WSAStartup(MAKEWORD(2, 2), &ws);
    sockfd = socket(AF_INET, SOCK_DGRAM, 0);

    // Set socket buffer size
    int buf_size = 1024 * 1024;
    setsockopt(sockfd, SOL_SOCKET, SO_RCVBUF, (char*)&buf_size, sizeof(buf_size));
    setsockopt(sockfd, SOL_SOCKET, SO_SNDBUF, (char*)&buf_size, sizeof(buf_size));

    memset(&servaddr, 0, sizeof(servaddr));
    servaddr.sin_family = AF_INET;
    inet_pton(AF_INET, svr, &servaddr.sin_addr);
    servaddr.sin_port = htons(port);

    cout << "Starting connection to " << svr << ":" << port << endl;
    cout << "Parameters: MSS=" << SENDER_MSS << " MAX_WINDOW=" << MAX_WINDOW
        << " RTO=" << RTO_MS << "ms LOSS=" << LOSS_PROB
        << " ClientWindow=" << CLIENT_ADVERTISED_WINDOW << endl;

    perform_handshake();

    // read file into memory
    ifstream ifs(file, ios::binary);
    if (!ifs) {
        cout << "open file failed" << endl;
        closesocket(sockfd);
        WSACleanup();
        return 1;
    }

    vector<char> filebuf((istreambuf_iterator<char>(ifs)), istreambuf_iterator<char>());
    size_t total = filebuf.size();
    cout << "file size=" << total << " bytes" << endl;

    // fragment into segments
    packets.clear();
    uint32_t off = 0;
    while (off < total) {
        Packet p;
        memset(&p.hdr, 0, sizeof(p.hdr));
        size_t take = min((size_t)SENDER_MSS, total - off);
        p.hdr.seq = off;
        p.hdr.len = (uint16_t)take;
        p.hdr.wnd = CLIENT_ADVERTISED_WINDOW;
        p.hdr.sack = sack_bitmap;
        p.data.assign(filebuf.begin() + off, filebuf.begin() + off + take);
        p.hdr.flags = 0;
        fill_checksum(&p.hdr, p.data.data());
        packets.push_back(move(p));
        off += (uint32_t)take;
    }

    // append last empty FIN packet
    Packet finp;
    memset(&finp.hdr, 0, sizeof(finp.hdr));
    finp.hdr.seq = (uint32_t)total;
    finp.hdr.len = 0;
    finp.hdr.flags = RDT_FIN;
    finp.hdr.wnd = CLIENT_ADVERTISED_WINDOW;
    finp.hdr.sack = sack_bitmap;
    fill_checksum(&finp.hdr, nullptr);
    packets.push_back(finp);

    cout << "Created " << packets.size() << " packets for transmission" << endl;

    // start recv thread
    thread recv_t(recv_thread_func);

    auto tstart = high_resolution_clock::now();

    // sending loop
    send_base = 0;
    size_t next_pkt_idx = 0;
    size_t pkt_count = packets.size();
    int packets_sent = 0;
    int window_updates = 0;

    while (true) {
        unique_lock<mutex> lk(mtx);

        // 新增：检查关闭状态
        if (close_state == CLOSE_WAIT_FIN_ACK) {
            // 已收到服务端FIN并发送了ACK，等待一会儿确保ACK到达
            cout << "[fin] waiting to ensure server received our ACK" << endl;
            this_thread::sleep_for(chrono::seconds(1));
            // 添加：通知接收线程结束
            {
                unique_lock<mutex> lk(mtx);
                finished = true;
            }
            cv.notify_all();  // 唤醒接收线程
            break;
        }

        // Calculate available window
        int allowed_window = min(cwnd, receiver_wnd);

        // Window status update every 500 packets sent
        if (packets_sent % 500 == 0 && packets_sent > 0) {
            cout << "[window#" << ++window_updates << "] cwnd=" << cwnd
                << " server_wnd=" << receiver_wnd
                << " allowed=" << allowed_window
                << " send_base=" << send_base
                << " in_flight=" << (next_pkt_idx - (send_base / SENDER_MSS))
                << " close_state=" << close_state << endl;
        }

        // Count in-flight packets
        int in_flight = 0;
        for (size_t i = 0; i < packets.size(); ++i) {
            if (!packets[i].acked && packets[i].sent_time.time_since_epoch().count() > 0) {
                in_flight++;
            }
        }

        // Send new packets while window allows
        while (in_flight < allowed_window && next_pkt_idx < pkt_count) {
            size_t idx = next_pkt_idx;
            Packet& p = packets[idx];

            // 新增：发送FIN时更新状态
            if (p.hdr.flags & RDT_FIN && close_state == CLOSE_IDLE) {
                close_state = CLOSE_FIN_SENT;
                cout << "[fin] sending FIN, entering close state" << endl;
            }

            // Update sack info before sending
            p.hdr.sack = sack_bitmap;
            p.hdr.wnd = CLIENT_ADVERTISED_WINDOW;
            fill_checksum(&p.hdr, p.data.data());

            p.sent_time = steady_clock::now();
            packets_sent++;

            if (p.hdr.len && !p.data.empty()) {
                vector<char> out(sizeof(RDTHeader) + p.data.size());
                RDTHeader th = p.hdr;
                hdr_hton(&th);
                memcpy(out.data(), &th, sizeof(RDTHeader));
                memcpy(out.data() + sizeof(RDTHeader), p.data.data(), p.data.size());
                send_with_optional_loss(out.data(), (int)out.size(), &servaddr);

                if (packets_sent % 200 == 0) {
                    cout << "[send#" << packets_sent << "] seq=" << p.hdr.seq
                        << " len=" << p.hdr.len
                        << " wnd=" << p.hdr.wnd
                        << " sack=0x" << hex << p.hdr.sack << dec << endl;
                }
            }
            else if (p.hdr.flags & RDT_FIN) {
                RDTHeader th = p.hdr;
                hdr_hton(&th);
                send_with_optional_loss((char*)&th, sizeof(RDTHeader), &servaddr);
                cout << "[send] FIN seq=" << p.hdr.seq << " wnd=" << p.hdr.wnd << endl;
            }

            next_pkt_idx++;
            in_flight++;
        }

        // wait for ACKs or timeout
        cv.wait_for(lk, milliseconds(20));

        // 新增：如果处于等待服务端FIN状态，设置更长的等待时间
        if (close_state == CLOSE_FIN_ACKED) {
            cv.wait_for(lk, milliseconds(100));
        }

        // check RTO for earliest unacked packet
        uint32_t earliest_seq = UINT32_MAX;
        int earliest_idx = -1;
        for (size_t i = 0; i < packets.size(); ++i) {
            if (!packets[i].acked) {
                if (packets[i].hdr.seq < earliest_seq) {
                    earliest_seq = packets[i].hdr.seq;
                    earliest_idx = (int)i;
                }
            }
        }

        if (earliest_idx >= 0) {
            auto& p = packets[earliest_idx];
            if (p.sent_time.time_since_epoch().count() > 0 &&
                duration_cast<milliseconds>(steady_clock::now() - p.sent_time).count() > RTO_MS) {

                // timeout retransmit
                ssthresh = max(1, cwnd / 2);
                cwnd = 1;
                cout << "[timeout] RTO triggered for seq=" << p.hdr.seq
                    << ", ssthresh=" << ssthresh << " cwnd=" << cwnd << endl;

                p.hdr.sack = sack_bitmap;
                p.hdr.wnd = CLIENT_ADVERTISED_WINDOW;
                fill_checksum(&p.hdr, p.data.data());

                p.sent_time = steady_clock::now();
                if (p.hdr.len && !p.data.empty()) {
                    vector<char> out(sizeof(RDTHeader) + p.data.size());
                    RDTHeader th = p.hdr;
                    hdr_hton(&th);
                    memcpy(out.data(), &th, sizeof(RDTHeader));
                    memcpy(out.data() + sizeof(RDTHeader), p.data.data(), p.data.size());
                    send_with_optional_loss(out.data(), (int)out.size(), &servaddr);
                    cout << "[retransmit] timeout seq=" << p.hdr.seq << endl;
                }
            }
        }

        // done condition: all packets acked
        bool allack = true;
        for (auto& p : packets) {
            if (!p.acked) {
                allack = false;
                break;
            }
        }

        if (allack) {
            cout << "[complete] All " << packets.size() << " packets acknowledged" << endl;
            // 如果已经发送了FIN但还没收到服务端FIN，继续等待
            if (close_state == CLOSE_FIN_ACKED || close_state == CLOSE_FIN_SENT) {
                cout << "[fin] waiting for server FIN..." << endl;

                // 使用循环等待，而不是单次等待
                auto wait_start = chrono::steady_clock::now();
                while (!received_server_fin) {
                    // 等待更长时间，比如10秒
                    if (chrono::duration_cast<chrono::seconds>(
                        chrono::steady_clock::now() - wait_start).count() > 10) {
                        cout << "[fin] timeout waiting for server FIN, closing anyway" << endl;
                        break;
                    }

                    // 等待并检查条件
                    cv.wait_for(lk, chrono::milliseconds(100));
                }
            }
            break;
        }
    }

    auto tend = high_resolution_clock::now();
    double ms = duration_cast<milliseconds>(tend - tstart).count();
    double seconds = ms / 1000.0;
    double bytes = (double)total;
    double mbps = seconds > 0 ? (bytes / seconds) / 1e6 : 0.0;

    cout << "\n========== Transmission Statistics ==========" << endl;
    cout << "Total packets sent: " << packets_sent << endl;
    cout << "File size: " << total << " bytes" << endl;
    cout << "Transmission time: " << ms << " ms" << endl;
    cout << "Throughput: " << mbps << " MB/s" << endl;
    cout << "Final cwnd: " << cwnd << endl;
    cout << "Final ssthresh: " << ssthresh << endl;
    cout << "Total ACKs received: " << total_acks_received << endl;
    cout << "Client advertised window: " << CLIENT_ADVERTISED_WINDOW << endl;
    cout << "Server advertised window: " << receiver_wnd << endl;
    cout << "Final close state: " << close_state << endl;
    cout << "============================================" << endl;

    cout << "\n[debug] Setting finished flag and notifying threads..." << endl;

    // 确保设置结束标志
    {
        unique_lock<mutex> lk(mtx);
        finished = true;
        cv.notify_all();
    }

    // 等待接收线程结束（最多等待2秒）
    cout << "[debug] Waiting for receiver thread to join..." << endl;
    auto join_start = chrono::steady_clock::now();

    while (recv_t.joinable()) {
        if (chrono::duration_cast<chrono::seconds>(
            chrono::steady_clock::now() - join_start).count() > 2) {
            cout << "[warning] Receiver thread not responding, detaching..." << endl;
            recv_t.detach();  // 强制分离线程
            break;
        }
        this_thread::sleep_for(chrono::milliseconds(100));
    }

    cout << "[debug] Cleanup complete, exiting program." << endl;

    closesocket(sockfd);
    WSACleanup();
    return 0;
}