#include <winsock2.h>
#include <ws2tcpip.h>
#include <iostream>
#include <string>
#include <vector>
#include <thread>
#include <mutex>
#include <chrono>
#include <unordered_map>
#include <format>
#include "DES.h"

#pragma comment(lib, "ws2_32.lib")

using namespace std;

// 存储客户端信息：socket字符串 -> 昵称
unordered_map<string, string> clientNames;
// 存储客户端信息：socket字符串 -> IP地址
unordered_map<string, string> clientIps;

// 全局加密密钥
string encryption_key;

void broadcastMessage(const vector<SOCKET>& clients, const char* message, SOCKET sender) {
    string formatted_msg = string(message);
    if (formatted_msg.back() != '\n') {
        formatted_msg += "\r\n";
    }

    // 如果消息不是系统广播（如用户加入消息），则添加发送者昵称
    bool is_system_msg = formatted_msg.find("has joined the chat room!") != string::npos ||
        formatted_msg.find("has left the chat room!") != string::npos;

    if (!is_system_msg && sender != INVALID_SOCKET) {
        string sender_str = to_string(sender);
        string sender_name = "Anonymous";

        // 查找发送者昵称
        auto it = clientNames.find(sender_str);
        if (it != clientNames.end()) {
            sender_name = it->second;
        }

        // 查找当前时间
        auto now = chrono::system_clock::now();

        // 直接获取格式化的时间字符串
        auto t = chrono::system_clock::to_time_t(now);
        tm tm_time;
        localtime_s(&tm_time, &t);
        char buf[32];
        strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &tm_time);
        string time_str(buf);

        formatted_msg = "<" + time_str + " " + sender_name + "> " + formatted_msg;
    }

    // 加密消息后广播
    string encrypted_msg = desEncryptString(formatted_msg, encryption_key);

    for (SOCKET client : clients) {
        if (client != sender) {
            if (send(client, encrypted_msg.c_str(), encrypted_msg.length(), 0) == SOCKET_ERROR) {
                cout << "Failed to send: " << WSAGetLastError() << endl;
            }
        }
    }
}


void acceptNewClient(SOCKET server_socket, vector<SOCKET>& clients, mutex& clients_mutex) {
    sockaddr_in client_addr;
    int client_addr_len = sizeof(client_addr);

    SOCKET client_socket = accept(server_socket, (sockaddr*)&client_addr, &client_addr_len);
    if (client_socket == INVALID_SOCKET) {
        cout << "accept failed: " << WSAGetLastError() << endl;
        return;
    }

    // 获取客户端IP地址
    char client_ip[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &client_addr.sin_addr, client_ip, INET_ADDRSTRLEN);

    // 设置客户端socket为非阻塞
    u_long mode = 1; // 1表示非阻塞
    ioctlsocket(client_socket, FIONBIO, &mode);

    {
        lock_guard<mutex> lock(clients_mutex);
        clients.push_back(client_socket);
    }

    // 存储客户端IP地址
    string socket_str = to_string(client_socket);
    clientIps[socket_str] = client_ip;

    cout << "New client connection: " << client_ip << ":" << ntohs(client_addr.sin_port)
        << ", the total number of clients: " << clients.size() << endl;

    // 发送客户端欢迎消息（需要加密）
    string tips = "===Welcome to the chat room. Current number of online users: " + to_string(clients.size()) + "===\r\n";
    string encrypted_tips = desEncryptString(tips, encryption_key);
    send(client_socket, encrypted_tips.c_str(), encrypted_tips.length(), 0);
}

void handleClientMessages(vector<SOCKET>& clients, mutex& clients_mutex) {
    for (auto it = clients.begin(); it != clients.end(); ) {
        SOCKET client_socket = *it;
        char buffer[1024];
        string socket_str = to_string(client_socket);

        // 检查是否有数据
        fd_set readfds;
        FD_ZERO(&readfds);
        FD_SET(client_socket, &readfds);
        timeval timeout = { 0, 0 }; // 立即返回

        int activity = select(0, &readfds, nullptr, nullptr, &timeout);
        if (activity > 0 && FD_ISSET(client_socket, &readfds)) {
            int bytes_received = recv(client_socket, buffer, sizeof(buffer) - 1, 0);

            if (bytes_received > 0) {
                // 成功接收数据
                buffer[bytes_received] = '\0';

                // 接收到的消息是加密的，需要解密
                string encrypted_data(buffer, bytes_received);
                string data = desDecryptString(encrypted_data, encryption_key);

                // 检查是否是昵称（用户的第一条消息）
                if (clientNames.find(socket_str) == clientNames.end()) {
                    // 这是昵称消息
                    string nickname = data;

                    // 去除可能的多余换行符
                    if (!nickname.empty() && nickname.back() == '\r') {
                        nickname.pop_back();
                    }
                    if (!nickname.empty() && nickname.back() == '\n') {
                        nickname.pop_back();
                    }

                    // 存储昵称信息
                    clientNames[socket_str] = nickname;

                    // 获取客户端IP
                    string client_ip = clientIps[socket_str];
                    cout << "Client " << client_ip << " registered with nickname: " << nickname << endl;

                    // 广播新用户加入消息
                    string join_msg = "===" + nickname + " has joined the chat room!===\r\n";
                    lock_guard<mutex> lock(clients_mutex);
                    broadcastMessage(clients, join_msg.c_str(), client_socket);
                }
                else {
                    // 这是普通聊天消息
                    cout << "Received the message from " << clientNames[socket_str] << ": " << data;

                    // 广播消息给其他客户端
                    lock_guard<mutex> lock(clients_mutex);
                    broadcastMessage(clients, data.c_str(), client_socket);
                }
                ++it;
            }
            else {
                // 客户端关闭连接
                string leaving_nickname = "Anonymous";

                // 获取离开的用户昵称
                auto it_name = clientNames.find(socket_str);
                if (it_name != clientNames.end()) {
                    leaving_nickname = it_name->second;
                    clientNames.erase(it_name);  // 从昵称映射中移除
                }

                // 移除IP信息
                clientIps.erase(socket_str);

                cout << "The client " << leaving_nickname << " is disconnected" << endl;

                // 先计算移除后的在线人数（减1，因为当前客户端还未移除）
                int online_count = clients.size() - 1;

                // 广播用户离开消息和在线人数
                string leave_msg = "===" + leaving_nickname + " has left the chat room!" + "Current number of online users: " + to_string(online_count) + "===" + "\r\n";
                lock_guard<mutex> lock(clients_mutex);
                broadcastMessage(clients, leave_msg.c_str(), INVALID_SOCKET);

                closesocket(client_socket);
                it = clients.erase(it);
            }
        }
        else {
            ++it;
        }
    }
}

int main()
{
    // 初始化加密密钥
    encryption_key = getEncryptionKey();
    cout << "Server using encryption key: " << encryption_key << endl;

    // 初始化WinSocket
    WSADATA wsaData;
    int result = WSAStartup(MAKEWORD(2, 2), &wsaData);
    if (result != 0) {
        cout << "WSAStartup failed: " << result << endl;
        return 1;
    }

    // 创建服务器套接字
    SOCKET server_socket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (server_socket == INVALID_SOCKET) {
        cout << "socket creation failed: " << WSAGetLastError() << endl;
        WSACleanup();
        return 1;
    }

    // 设置套接字选项
    int opt = 1;
    if (setsockopt(server_socket, SOL_SOCKET, SO_REUSEADDR, (char*)&opt, sizeof(opt)) == SOCKET_ERROR) {
        cout << "setsockopt failed: " << WSAGetLastError() << endl;
        closesocket(server_socket);
        WSACleanup();
        return 1;
    }

    // 绑定地址和端口
    sockaddr_in server_addr;
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;  // 所有网络接口
    server_addr.sin_port = htons(8080);        // 端口8080

    if (bind(server_socket, (sockaddr*)&server_addr, sizeof(server_addr)) == SOCKET_ERROR) {
        cout << "bind failed: " << WSAGetLastError() << endl;
        closesocket(server_socket);
        WSACleanup();
        return 1;
    }

    // 监听客户端连接
    if (listen(server_socket, SOMAXCONN) == SOCKET_ERROR) {
        cout << "listen failed: " << WSAGetLastError() << endl;
        closesocket(server_socket);
        WSACleanup();
        return 1;
    }

    cout << "The server has started successfully and is listening on port 8080..." << endl;

    // 存储所有客户端socket
    vector<SOCKET> clients;
    mutex clients_mutex;
    bool running = true;

    while (running) {
        // 监听服务器socket和所有客户端socket
        fd_set readfds;
        FD_ZERO(&readfds);
        FD_SET(server_socket, &readfds);

        SOCKET max_fd = server_socket;

        // 添加所有客户端socket到集合
        {
            lock_guard<mutex> lock(clients_mutex);
            for (SOCKET client : clients) {
                FD_SET(client, &readfds);
                if (client > max_fd) max_fd = client;
            }
        }

        // 设置超时
        timeval timeout;
        timeout.tv_sec = 1;
        timeout.tv_usec = 0;

        // 等待活动
        int activity = select(0, &readfds, nullptr, nullptr, &timeout);

        if (activity == SOCKET_ERROR) {
            cout << "select error: " << WSAGetLastError() << endl;
            break;
        }

        if (activity > 0) {
            // 处理新连接
            if (FD_ISSET(server_socket, &readfds)) {
                acceptNewClient(server_socket, clients, clients_mutex);
            }

            // 处理客户端消息
            handleClientMessages(clients, clients_mutex);
        }
    }

    // 关闭所有客户端连接
    for (SOCKET client : clients) {
        closesocket(client);
    }

    // 关闭服务器socket
    closesocket(server_socket);

    // 清理Winsock  
    WSACleanup();

    return 0;
}