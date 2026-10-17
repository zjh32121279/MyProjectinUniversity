#include "../RDT.h"
#include <iostream>
#include <vector>
#include <map>
#include <fstream>
#include <thread>
#include <chrono>

using namespace std;

SOCKET sockfd = INVALID_SOCKET;
uint32_t recv_base = 0;
int recv_wnd = 32;
map<uint32_t, vector<char>> out_of_order;

// 添加：连接状态标志
bool connection_closing = false;  // 新增：表示正在关闭连接
bool fin_sent = false;            // 新增：是否已发送FIN
uint32_t fin_seq = 0;             // 新增：发送的FIN的序列号

void send_ack(const SOCKADDR_IN& cli, uint32_t acknum) {
    RDTHeader h;
    memset(&h, 0, sizeof(h));
    h.seq = 0;
    h.ack = acknum;
    h.flags = RDT_ACK;
    h.wnd = recv_wnd;

    // build sack bitmap for next 32 segments beyond acknum
    uint32_t mask = 0;
    for (int i = 0; i < RDT_MAX_SACK_BITS; i++) {
        uint32_t s = acknum + i * RDT_MSS;
        if (out_of_order.count(s)) mask |= (1u << i);
    }
    h.sack = mask;

    fill_checksum(&h, nullptr);
    RDTHeader neth = h;
    hdr_hton(&neth);
    sendto(sockfd, (char*)&neth, sizeof(neth), 0, (sockaddr*)&cli, sizeof(cli));
}

// 新增：发送FIN函数
void send_fin(const SOCKADDR_IN& cli) {
    RDTHeader h;
    memset(&h, 0, sizeof(h));
    h.seq = 100;  // 服务端序列号起始值
    h.ack = recv_base;
    h.flags = RDT_FIN | RDT_ACK;
    h.wnd = recv_wnd;
    h.sack = 0;
    
    fill_checksum(&h, nullptr);
    RDTHeader neth = h;
    hdr_hton(&neth);
    sendto(sockfd, (char*)&neth, sizeof(neth), 0, (sockaddr*)&cli, sizeof(cli));
    
    cout << "[fin] sent FIN, seq=" << h.seq << " ack=" << h.ack << endl;
    fin_sent = true;
    fin_seq = h.seq;
}

int main(int argc, char** argv) {
    if (argc < 2) {
        cout << "Usage: RDTServer <port> [--wnd N]" << endl;
        cout << "  port: port number to listen" << endl;
        cout << "  --wnd N: receiver window size in segments (default 32)" << endl;
        return 1;
    }

    int port = atoi(argv[1]);

    for (int i = 2; i < argc; ++i) {
        string arg = argv[i];
        if (arg == "--wnd" && i + 1 < argc) {
            recv_wnd = atoi(argv[++i]);
            if (recv_wnd <= 0) recv_wnd = 1;
            cout << "Set receiver window size to: " << recv_wnd << " segments" << endl;
        }
        else if (arg == "--help" || arg == "-h") {
            cout << "Usage: RDTServer <port> [--wnd N]" << endl;
            return 0;
        }
    }

    WSAData ws;
    WSAStartup(MAKEWORD(2, 2), &ws);
    sockfd = socket(AF_INET, SOCK_DGRAM, 0);

    int recv_buf_size = 1024 * 1024;
    setsockopt(sockfd, SOL_SOCKET, SO_RCVBUF, (char*)&recv_buf_size, sizeof(recv_buf_size));

    SOCKADDR_IN serv;
    memset(&serv, 0, sizeof(serv));
    serv.sin_family = AF_INET;
    serv.sin_addr.s_addr = htonl(INADDR_ANY);
    serv.sin_port = htons(port);

    if (bind(sockfd, (sockaddr*)&serv, sizeof(serv)) == SOCKET_ERROR) {
        cerr << "Bind failed: " << LastWSAError() << endl;
        closesocket(sockfd);
        WSACleanup();
        return 1;
    }

    cout << "Server listening on port " << port << ", receiver window=" << recv_wnd << " segments" << endl;

    char buf[sizeof(RDTHeader) + RDT_MSS];
    SOCKADDR_IN cli;
    int clilen = sizeof(cli);

    bool connected = false;

    // Three-way handshake
    while (!connected) {
        int r = recvfrom(sockfd, buf, sizeof(buf), 0, (sockaddr*)&cli, &clilen);
        if (r <= 0) continue;

        if (r < (int)sizeof(RDTHeader)) {
            cout << "[handshake] packet too small" << endl;
            continue;
        }

        if (!verify_checksum_raw(buf, r)) {
            cout << "[handshake] checksum failed" << endl;
            continue;
        }

        RDTHeader h;
        memcpy(&h, buf, sizeof(RDTHeader));
        hdr_ntoh(&h);

        if (h.flags & RDT_SYN) {
            cout << "[handshake] received SYN, wnd=" << h.wnd << endl;

            // reply SYN+ACK
            RDTHeader rh;
            memset(&rh, 0, sizeof(rh));
            rh.seq = 100;
            rh.ack = h.seq + 1;
            rh.flags = RDT_SYN | RDT_ACK;
            rh.wnd = recv_wnd;
            fill_checksum(&rh, nullptr);
            RDTHeader neth = rh;
            hdr_hton(&neth);
            sendto(sockfd, (char*)&neth, sizeof(neth), 0, (sockaddr*)&cli, clilen);

            cout << "[handshake] sent SYN+ACK, wnd=" << rh.wnd << endl;
        }
        else if ((h.flags & RDT_ACK) && h.ack) {
            connected = true;
            cout << "[handshake] complete, client wnd=" << h.wnd << endl;
        }
    }

    vector<char> output;
    auto last_active = chrono::steady_clock::now();
    int total_packets = 0;
    int truncated_packets = 0;
    int out_of_order_count = 0;

    while (true) {
        // 如果正在关闭连接且已发送FIN，等待对FIN的ACK
        if (connection_closing && fin_sent) {
            // 简化的等待：检查是否有数据到达
            cout << "[fin] waiting for ACK to our FIN..." << endl;
            this_thread::sleep_for(chrono::milliseconds(100));
            
            // 等待1秒后退出
            static auto fin_sent_time = chrono::steady_clock::now();
            if (chrono::duration_cast<chrono::seconds>(
                chrono::steady_clock::now() - fin_sent_time).count() > 1) {
                cout << "[fin] timeout, assuming ACK lost, closing anyway" << endl;
                break;
            }
        }

        int r = recvfrom(sockfd, buf, sizeof(buf), 0, (sockaddr*)&cli, &clilen);
        if (r <= 0) {
            this_thread::sleep_for(chrono::milliseconds(5));
            if (chrono::duration_cast<chrono::seconds>(chrono::steady_clock::now() - last_active).count() > 300) {
                cout << "Timeout, closing connection" << endl;
                break;
            }
            continue;
        }

        last_active = chrono::steady_clock::now();
        total_packets++;

        // Check packet size
        if (r < (int)sizeof(RDTHeader)) {
            cout << "[error] packet too small: " << r << " bytes" << endl;
            truncated_packets++;
            continue;
        }

        // Verify checksum
        if (!verify_checksum_raw(buf, r)) {
            cout << "[error] checksum failed" << endl;
            continue;
        }

        // Parse header
        RDTHeader h;
        memcpy(&h, buf, sizeof(RDTHeader));
        hdr_ntoh(&h);

        // Check packet length matches header
        if (r < (int)(sizeof(RDTHeader) + h.len)) {
            cout << "[error] truncated packet: header len=" << h.len
                << ", expected " << (sizeof(RDTHeader) + h.len)
                << " bytes, got " << r << " bytes" << endl;
            truncated_packets++;
            continue;
        }

        // Print packet info (only important details)
        if (h.flags & RDT_FIN) {
            cout << "[recv] FIN seq=" << h.seq << " ack=" << h.ack 
                << " wnd=" << h.wnd << " sack=0x" << hex << h.sack << dec << endl;
        }
        else if (h.flags & RDT_RST) {
            cout << "[recv] RST received, closing connection immediately" << endl;
            break;
        }
        else {
            cout << "[recv] data seq=" << h.seq << " len=" << h.len
                << " ack=" << h.ack << " wnd=" << h.wnd 
                << " sack=0x" << hex << h.sack << dec << endl;
        }

        const char* payload = nullptr;
        if (h.len) payload = buf + sizeof(RDTHeader);

        // 修改：处理FIN（四次挥手的第一步）
        if (h.flags & RDT_FIN) {
            if (!connection_closing) {
                cout << ">>> Received FIN, sending ACK and preparing to close" << endl;
                // 第一步：发送ACK确认客户端的FIN
                send_ack(cli, h.seq + 1);
                
                // 标记开始关闭流程
                connection_closing = true;
                
                // 注意：这里不立即break，继续处理可能有的数据
            }
        }
        
        // 新增：处理对服务端FIN的ACK（四次挥手的第四步）
        if ((h.flags & RDT_ACK) && connection_closing && fin_sent) {
            if (h.ack == fin_seq + 1) {
                cout << ">>> Received ACK for our FIN, connection closed" << endl;
                // 等待一段时间（简化的TIME_WAIT）
                this_thread::sleep_for(chrono::milliseconds(500));
                break;
            }
        }

        // Process data (只在未开始关闭或刚收到FIN时处理数据)
        if (!connection_closing || (h.flags & RDT_FIN)) {
            if (h.seq == recv_base) {
                // in-order delivery
                if (h.len && payload) {
                    output.insert(output.end(), payload, payload + h.len);
                }
                recv_base += h.len ? h.len : 1;

                // Deliver buffered packets
                while (out_of_order.count(recv_base)) {
                    auto& v = out_of_order[recv_base];
                    output.insert(output.end(), v.begin(), v.end());
                    recv_base += (uint32_t)v.size();
                    out_of_order.erase(recv_base - (uint32_t)v.size());
                    out_of_order_count--;
                }

                send_ack(cli, recv_base);
            }
            else if (h.seq > recv_base) {
                // out-of-order
                if (!out_of_order.count(h.seq) && h.len && payload) {
                    vector<char> v(payload, payload + h.len);
                    out_of_order[h.seq] = move(v);
                    out_of_order_count++;
                }
                send_ack(cli, recv_base);
            }
            else {
                // duplicate
                send_ack(cli, recv_base);
            }
        }

        // 新增：如果已经开始关闭且没有待处理的数据，发送服务端的FIN
        if (connection_closing && !fin_sent) {
            // 检查是否所有数据都已处理（简化检查：没有乱序包）
            if (out_of_order.empty()) {
                cout << "[fin] all data processed, sending our FIN" << endl;
                send_fin(cli);
            }
        }

        // Status update every 100 packets
        if (total_packets % 100 == 0) {
            cout << "[status] packets=" << total_packets
                << " recv_base=" << recv_base
                << " buffered=" << out_of_order_count 
                << " closing=" << (connection_closing ? "yes" : "no") << endl;
        }
    }

    // Write file
    ofstream ofs("received.bin", ios::binary);
    if (ofs) {
        ofs.write(output.data(), (streamsize)output.size());
        ofs.close();
        cout << "Successfully wrote received.bin, size=" << output.size() << " bytes" << endl;
    }

    // Statistics
    cout << "\n========== Reception Statistics ==========" << endl;
    cout << "Total packets received: " << total_packets << endl;
    cout << "Truncated packets: " << truncated_packets << endl;
    cout << "Max out-of-order buffered: " << out_of_order_count << endl;
    cout << "Output file size: " << output.size() << " bytes" << endl;
    cout << "==========================================" << endl;

    closesocket(sockfd);
    WSACleanup();
    return 0;
}