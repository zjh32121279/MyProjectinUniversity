#include <winsock2.h>
#include <ws2tcpip.h>
#include <iostream>
#include <string>
#include <thread>
#include <atomic>
#include <chrono>

#pragma comment(lib, "ws2_32.lib")

using namespace std;

int main() {
    // 初始化WinSock
    WSADATA wsaData;
    if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
        cout << "WSAStartup failed" << endl;
        return 1;
    }

    // 创建客户端socket
    SOCKET client_socket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (client_socket == INVALID_SOCKET) {
        cout << "socket creation failed: " << WSAGetLastError() << endl;
        WSACleanup();
        return 1;
    }

    // 设置服务器地址
    sockaddr_in server_addr;
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(8080);  // 服务器端口号

    // 将IP地址字符串转换为二进制形式
    if (inet_pton(AF_INET, "127.0.0.1", &server_addr.sin_addr) != 1) {
        cout << "Invalid IP address" << endl;
        closesocket(client_socket);
        WSACleanup();
        return 1;
    }

    // 连接到服务器
    if (connect(client_socket, (sockaddr*)&server_addr, sizeof(server_addr)) == SOCKET_ERROR) {
        cout << "Failed connection to the server: " << WSAGetLastError() << endl;
        closesocket(client_socket);
        WSACleanup();
        return 1;
    }

    cout << "Successfully connected to the server!" << endl;

    // 设置客户端socket为非阻塞模式
    u_long mode = 1; // 1表示非阻塞
    ioctlsocket(client_socket, FIONBIO, &mode);

    // 开始接收消息
    atomic<bool> connected{ true };

    // 接收服务器消息的线程
    auto receiveFunc = [&]() {
        char buffer[1024];
        while (connected) {
            // 使用select检查是否有数据可读，避免阻塞
            fd_set readfds;
            FD_ZERO(&readfds);
            FD_SET(client_socket, &readfds);
            timeval timeout = { 0, 100000 }; // 100毫秒超时

            int activity = select(0, &readfds, nullptr, nullptr, &timeout);
            
            if (activity > 0 && FD_ISSET(client_socket, &readfds)) {
                int bytes_received = recv(client_socket, buffer, sizeof(buffer) - 1, 0);

                if (bytes_received > 0) {
                    buffer[bytes_received] = '\0';
                    cout << buffer;
                }
                else if (bytes_received == 0) {
                    cout << "\nThe server is disconnected." << endl;
                    connected = false;
                    break;
                }
                else {
                    // 非阻塞模式下，WSAEWOULDBLOCK是正常的，不是错误
                    int error_code = WSAGetLastError();
                    if (error_code != WSAEWOULDBLOCK) {
                        cout << "\nReception error: " << error_code << endl;
                        connected = false;
                        break;
                    }
                }
            }
            // 如果select超时，继续循环检查connected标志
        }
    };
    
    // 启动接收线程
    thread receiver(receiveFunc);
    
    // 输入昵称
    cout << "Please enter your nickname(Length not exceeding 1024):\r\n";
    string client_name;
    getline(cin, client_name);
    while( client_name.length() > 1024) {
        cout << "Invalid nickname. Please enter a nickname with length not exceeding 1024:\r\n";
        getline(cin, client_name);
    }
    if (client_name.length() == 0) {
        auto now = chrono::system_clock::now();
        auto timestamp_s = chrono::duration_cast<chrono::seconds>(now.time_since_epoch());
        client_name = to_string(timestamp_s.count());
    }
    send(client_socket, client_name.c_str(), client_name.length(), 0);

    // 处理输入和接收消息
    string message;
    while (connected) {
        getline(cin, message);

        if (!connected) break;

        if (message == "/quit") {
            connected = false;
            break;
        }

        // 发送消息到服务器
        message += "\r\n";

        if (send(client_socket, message.c_str(), message.length(), 0) == SOCKET_ERROR) {
            cout << "Failed to send: " << WSAGetLastError() << endl;
            connected = false;
            break;
        }
    }

    // 等待接收线程结束 
    if (receiver.joinable()) {
        receiver.join();
    }

    // 关闭客户端socket
    closesocket(client_socket);

    // 清理Winsock  
    WSACleanup();

    cout << "The client has exited" << endl;
}