#include <iostream>
#include <string>
#include <vector>
#include <thread>
#include <mutex>
#include <chrono>
#include <unordered_map>
#include <cstring>
#include <cerrno>
#include <sys/socket.h>
#include <sys/select.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>
#include "RSA.h"
#include "DES.h"

using namespace std;

// Store client information
unordered_map<int, string> clientNames;
unordered_map<int, string> clientIps;
unordered_map<int, string> clientDESkey;
unordered_map<int, bool> awaitingDESKey;
unordered_map<int, string> clientRecvBuf;  // per-client receive buffer for TCP stream reassembly
string cachedPubKeyStr;

// Global client list and mutex
vector<int> g_clients;
mutex g_clients_mutex;

// Broadcast message to all clients (except sender)
void broadcastMessage(const string& message, int sender) {
    lock_guard<mutex> lock(g_clients_mutex);

    string formatted_msg = message;
    if (formatted_msg.back() != '\n') {
        formatted_msg += "\r\n";
    }

    cout << "Broadcasting to " << g_clients.size() << " clients (sender=" << sender << ")" << endl;
    cout << "Message content: " << formatted_msg;

    for (int client : g_clients) {
        if (client != sender) {
            auto it = clientDESkey.find(client);
            if (it != clientDESkey.end() && !it->second.empty()) {
                string encryptedMsg = desEncryptString(formatted_msg, it->second);
                // Base64-encode to make binary ciphertext safe for \r\n-delimited protocol
                string encodedMsg = base64Encode(encryptedMsg) + "\r\n";

                if (send(client, encodedMsg.c_str(), encodedMsg.length(), 0) == -1) {
                    if (errno != EAGAIN && errno != EWOULDBLOCK) {
                        cout << "Failed to send to client " << client << ": " << strerror(errno) << endl;
                    }
                } else {
                    cout << "Successfully sent to client " << client << endl;
                }
            } else {
                cout << "No DES key for client " << client << ", sending plaintext" << endl;
                if (send(client, formatted_msg.c_str(), formatted_msg.length(), 0) == -1) {
                    if (errno != EAGAIN && errno != EWOULDBLOCK) {
                        cout << "Failed to send to client " << client << ": " << strerror(errno) << endl;
                    }
                }
            }
        }
    }
}

void sendToClient(int client_socket, const string& message) {
    string formatted_msg = message;
    if (formatted_msg.back() != '\n') {
        formatted_msg += "\r\n";
    }

    auto it = clientDESkey.find(client_socket);
    if (it != clientDESkey.end() && !it->second.empty()) {
        string encryptedMsg = desEncryptString(formatted_msg, it->second);
        // Base64-encode to make binary ciphertext safe for \r\n-delimited protocol
        string encodedMsg = base64Encode(encryptedMsg) + "\r\n";
        send(client_socket, encodedMsg.c_str(), encodedMsg.length(), 0);
    } else {
        send(client_socket, formatted_msg.c_str(), formatted_msg.length(), 0);
    }
}

// Set socket to non-blocking mode
void setNonBlocking(int sock) {
    int flags = fcntl(sock, F_GETFL, 0);
    fcntl(sock, F_SETFL, flags | O_NONBLOCK);
}

// Handle DES key received from client
bool handleDESKey(int client_socket, const string& encryptedKey, const string& privKeyFile) {
    string decryptedKey = rsaDecrypt(encryptedKey, privKeyFile);

    if (decryptedKey.length() != 8) {
        cout << "Invalid DES key length: " << decryptedKey.length() << " bytes" << endl;
        return false;
    }

    clientDESkey[client_socket] = decryptedKey;
    awaitingDESKey[client_socket] = false;

    cout << "DES key received and stored for client " << client_socket << endl;

    sendToClient(client_socket, "[DESKEY_OK]");

    return true;
}

// Accept new client connection
void acceptNewClient(int server_socket) {
    sockaddr_in client_addr;
    socklen_t client_addr_len = sizeof(client_addr);
    int client_socket = accept(server_socket, (sockaddr*)&client_addr, &client_addr_len);
    if (client_socket == -1) {
        cout << "accept failed: " << strerror(errno) << endl;
        return;
    }

    char client_ip[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &client_addr.sin_addr, client_ip, INET_ADDRSTRLEN);
    setNonBlocking(client_socket);

    {
        lock_guard<mutex> lock(g_clients_mutex);
        g_clients.push_back(client_socket);
    }

    clientIps[client_socket] = client_ip;
    awaitingDESKey[client_socket] = true;
    clientRecvBuf[client_socket] = "";  // Initialize receive buffer

    cout << "New client connection: " << client_ip << ":" << ntohs(client_addr.sin_port)
         << ", total clients: " << g_clients.size() << endl;

    // Send welcome message (plaintext, no DES key yet)
    string tips = "=== Welcome to the chat room! ===\r\n";
    sendToClient(client_socket, tips);

    // Send public key
    string header = "[PUBKEY_BEGIN]" + to_string(cachedPubKeyStr.length()) + "[PUBKEY_END]";
    send(client_socket, header.c_str(), header.length(), 0);
    send(client_socket, cachedPubKeyStr.c_str(), cachedPubKeyStr.length(), 0);

    cout << "Sent public key to client " << client_ip << endl;
}

// Handle client disconnect
void handleClientDisconnect(int client_socket) {
    string leaving_nickname = "Anonymous";
    auto it_name = clientNames.find(client_socket);
    if (it_name != clientNames.end()) {
        leaving_nickname = it_name->second;
        clientNames.erase(it_name);
    }

    clientIps.erase(client_socket);
    clientDESkey.erase(client_socket);
    awaitingDESKey.erase(client_socket);
    clientRecvBuf.erase(client_socket);

    // Remove from global list
    {
        lock_guard<mutex> lock(g_clients_mutex);
        for (auto it = g_clients.begin(); it != g_clients.end(); ++it) {
            if (*it == client_socket) {
                g_clients.erase(it);
                break;
            }
        }
    }

    cout << "Client " << leaving_nickname << " disconnected, remaining: " << g_clients.size() << endl;

    int online_count = g_clients.size();
    string leave_msg = "=== " + leaving_nickname + " has left the chat room! Current online users: "
                     + to_string(online_count) + " ===\r\n";
    broadcastMessage(leave_msg, -1);

    close(client_socket);
}

// Process a single complete message (delimited by \r\n) from a client
void processMessage(int client_socket, const string& data) {
    // Check for DES key message
    size_t key_start = data.find("[DESKEY_BEGIN]");
    size_t key_end = data.find("[DESKEY_END]");

    if (key_start != string::npos && key_end != string::npos) {
        size_t encrypted_start = key_start + strlen("[DESKEY_BEGIN]");
        string encryptedKey = data.substr(encrypted_start, key_end - encrypted_start);
        handleDESKey(client_socket, encryptedKey, "private.key");
        return;
    }

    // If still awaiting DES key, ignore other messages
    if (awaitingDESKey[client_socket]) {
        return;
    }

    // Base64-decode then DES-decrypt the message
    string decryptedData;
    try {
        string rawCiphertext = base64Decode(data);
        if (rawCiphertext.empty()) {
            cout << "Base64 decode returned empty for client " << client_socket << endl;
            return;
        }
        decryptedData = desDecryptString(rawCiphertext, clientDESkey[client_socket]);
    } catch (const exception& e) {
        cout << "Decryption error from client " << client_socket << ": " << e.what() << endl;
        return;
    }

    if (decryptedData.empty()) {
        cout << "Decryption returned empty for client " << client_socket << endl;
        return;
    }

    // Strip trailing \r\n
    while (!decryptedData.empty() &&
           (decryptedData.back() == '\r' || decryptedData.back() == '\n')) {
        decryptedData.pop_back();
    }

    if (decryptedData.empty()) return;

    // Check if this is the nickname (first message from client)
    if (clientNames.find(client_socket) == clientNames.end()) {
        string nickname = decryptedData;
        clientNames[client_socket] = nickname;

        string client_ip = clientIps[client_socket];
        cout << "Client " << client_ip << " registered with nickname: " << nickname << endl;

        int online_count = g_clients.size();
        string join_msg = "=== " + nickname + " has joined the chat room! Current online users: "
                        + to_string(online_count) + " ===\r\n";
        broadcastMessage(join_msg, client_socket);

        // Send welcome message to the new user
        string welcome = "=== Welcome " + nickname + "! ===\r\n";
        sendToClient(client_socket, welcome);
    } else {
        // Normal chat message
        string sender_name = clientNames[client_socket];
        cout << "Message from " << sender_name << ": " << decryptedData << endl;

        auto now = chrono::system_clock::now();
        auto t = chrono::system_clock::to_time_t(now);
        tm tm_time;
        localtime_r(&t, &tm_time);
        char buf[32];
        strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &tm_time);
        string time_str(buf);

        string formatted_msg = "<" + time_str + " " + sender_name + "> " + decryptedData + "\r\n";
        broadcastMessage(formatted_msg, client_socket);
    }
}

// Handle client messages with proper TCP stream buffering
void handleClientMessages() {
    while (true) {
        // Get a copy of the current client list
        vector<int> clients_copy;
        {
            lock_guard<mutex> lock(g_clients_mutex);
            clients_copy = g_clients;
        }

        if (clients_copy.empty()) {
            this_thread::sleep_for(chrono::milliseconds(100));
            continue;
        }

        // Set up select file descriptor set
        fd_set readfds;
        FD_ZERO(&readfds);
        int max_fd = 0;

        for (int client : clients_copy) {
            FD_SET(client, &readfds);
            if (client > max_fd) max_fd = client;
        }

        timeval timeout = {0, 100000}; // 100ms

        int activity = select(max_fd + 1, &readfds, nullptr, nullptr, &timeout);

        if (activity > 0) {
            // Check each client for incoming data
            for (int client_socket : clients_copy) {
                if (FD_ISSET(client_socket, &readfds)) {
                    char buffer[2048];
                    int bytes_received = recv(client_socket, buffer, sizeof(buffer) - 1, 0);

                    if (bytes_received > 0) {
                        buffer[bytes_received] = '\0';
                        string data(buffer, bytes_received);

                        // Accumulate in per-client receive buffer
                        clientRecvBuf[client_socket] += data;

                        // Process all complete messages (delimited by \r\n)
                        string& buf = clientRecvBuf[client_socket];
                        size_t pos;
                        while ((pos = buf.find("\r\n")) != string::npos) {
                            string message = buf.substr(0, pos);
                            buf = buf.substr(pos + 2); // Remove processed message + delimiter

                            if (!message.empty()) {
                                processMessage(client_socket, message);
                            }
                        }
                    }
                    else if (bytes_received == 0) {
                        // Client disconnected
                        clientRecvBuf.erase(client_socket);
                        handleClientDisconnect(client_socket);
                    }
                    else {
                        // Error
                        if (errno != EAGAIN && errno != EWOULDBLOCK) {
                            cout << "Receive error from client " << client_socket << ": " << strerror(errno) << endl;
                            clientRecvBuf.erase(client_socket);
                            handleClientDisconnect(client_socket);
                        }
                    }
                }
            }
        }
    }
}

int main() {
    // RSA key initialization
    string pubFile = "public.key";
    string privFile = "private.key";

    cout << "Generating RSA keys (this may take a few seconds)..." << endl;
    generateRSAKeys(2048, pubFile, privFile);

    cachedPubKeyStr = getKeyAsString(pubFile);
    cout << "RSA keys generated. Public key length: " << cachedPubKeyStr.length() << " bytes" << endl;

    // Create server socket
    int server_socket = socket(AF_INET, SOCK_STREAM, 0);
    if (server_socket == -1) {
        cout << "socket creation failed: " << strerror(errno) << endl;
        return 1;
    }

    int opt = 1;
    if (setsockopt(server_socket, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) == -1) {
        cout << "setsockopt failed: " << strerror(errno) << endl;
        close(server_socket);
        return 1;
    }

    sockaddr_in server_addr;
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons(8080);

    if (bind(server_socket, (sockaddr*)&server_addr, sizeof(server_addr)) == -1) {
        cout << "bind failed: " << strerror(errno) << endl;
        close(server_socket);
        return 1;
    }

    if (listen(server_socket, SOMAXCONN) == -1) {
        cout << "listen failed: " << strerror(errno) << endl;
        close(server_socket);
        return 1;
    }

    cout << "Server started successfully, listening on port 8080..." << endl;
    cout << "========================================" << endl;

    // Start client message handling thread
    thread messageHandler(handleClientMessages);

    // Main loop: accept new connections
    while (true) {
        fd_set readfds;
        FD_ZERO(&readfds);
        FD_SET(server_socket, &readfds);

        timeval timeout = {1, 0};

        int activity = select(server_socket + 1, &readfds, nullptr, nullptr, &timeout);

        if (activity > 0 && FD_ISSET(server_socket, &readfds)) {
            acceptNewClient(server_socket);
        }
    }

    // Cleanup (never reached in practice)
    messageHandler.detach();
    close(server_socket);

    return 0;
}
