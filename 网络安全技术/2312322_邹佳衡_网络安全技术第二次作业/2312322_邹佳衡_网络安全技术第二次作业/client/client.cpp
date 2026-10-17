#include <iostream>
#include <string>
#include <thread>
#include <atomic>
#include <chrono>
#include <cstring>
#include <cerrno>
#include <fstream>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>
#include "RSA.h"
#include "DES.h"

using namespace std;

atomic<bool> connected{true};
string desKey;
int client_socket;

void setNonBlocking(int sock) {
    int flags = fcntl(sock, F_GETFL, 0);
    fcntl(sock, F_SETFL, flags | O_NONBLOCK);
}

bool sendDESKey(const string& pubKeyFile) {
    string encryptedKey = rsaEncrypt(desKey, pubKeyFile);
    string keyMsg = "[DESKEY_BEGIN]" + encryptedKey + "[DESKEY_END]\r\n";

    if (send(client_socket, keyMsg.c_str(), keyMsg.length(), 0) == -1) {
        cout << "Failed to send DES key: " << strerror(errno) << endl;
        return false;
    }

    cout << "DES key sent to server (RSA encrypted)" << endl;
    return true;
}

bool receivePublicKey() {
    cout << "Waiting for public key from server..." << endl;

    string full_received_data;
    string pubkey_str = "";
    bool header_parsed = false;
    int expected_pubkey_len = 0;

    while (connected && !header_parsed) {
        char buffer[4096];
        fd_set readfds;
        FD_ZERO(&readfds);
        FD_SET(client_socket, &readfds);
        timeval timeout = {5, 0};

        int activity = select(client_socket + 1, &readfds, nullptr, nullptr, &timeout);
        if (activity > 0 && FD_ISSET(client_socket, &readfds)) {
            int bytes = recv(client_socket, buffer, sizeof(buffer) - 1, 0);

            if (bytes > 0) {
                buffer[bytes] = '\0';
                full_received_data += buffer;

                if (!header_parsed) {
                    size_t start_pos = full_received_data.find("[PUBKEY_BEGIN]");
                    size_t end_pos = full_received_data.find("[PUBKEY_END]");

                    if (start_pos != string::npos && end_pos != string::npos) {
                        size_t len_start = start_pos + strlen("[PUBKEY_BEGIN]");
                        string len_str = full_received_data.substr(len_start, end_pos - len_start);
                        expected_pubkey_len = stoi(len_str);

                        cout << "Expected pubkey length: " << expected_pubkey_len << " bytes" << endl;
                        header_parsed = true;

                        size_t pubkey_start = end_pos + strlen("[PUBKEY_END]");
                        if (full_received_data.length() > pubkey_start) {
                            pubkey_str = full_received_data.substr(pubkey_start);
                        }
                    }
                } else {
                    // Still collecting pubkey data
                    size_t end_pos = full_received_data.find("[PUBKEY_END]");
                    if (end_pos != string::npos) {
                        size_t pubkey_start = end_pos + strlen("[PUBKEY_END]");
                        if (full_received_data.length() > pubkey_start) {
                            pubkey_str = full_received_data.substr(pubkey_start);
                        }
                    }
                }

                if (header_parsed && (int)pubkey_str.length() >= expected_pubkey_len) {
                    pubkey_str = pubkey_str.substr(0, expected_pubkey_len);
                    saveKeyFromString(pubkey_str, "public.key");
                    cout << "Public key received and saved (" << pubkey_str.length() << " bytes)" << endl;
                    return true;
                }
            } else if (bytes == 0) {
                cout << "Server disconnected during handshake." << endl;
                return false;
            }
        } else {
            cout << "Wait for public key timeout." << endl;
            return false;
        }
    }

    return false;
}

void receiveFunction() {
    string recvBuffer;

    while (connected) {
        fd_set readfds;
        FD_ZERO(&readfds);
        FD_SET(client_socket, &readfds);
        timeval timeout = {0, 100000};

        int activity = select(client_socket + 1, &readfds, nullptr, nullptr, &timeout);

        if (activity > 0 && FD_ISSET(client_socket, &readfds)) {
            char buffer[2048];
            int bytes_received = recv(client_socket, buffer, sizeof(buffer) - 1, 0);

            if (bytes_received > 0) {
                buffer[bytes_received] = '\0';
                string receivedData(buffer, bytes_received);

                // Accumulate in receive buffer
                recvBuffer += receivedData;

                // Process all complete messages (delimited by \r\n)
                size_t pos;
                while ((pos = recvBuffer.find("\r\n")) != string::npos) {
                    string message = recvBuffer.substr(0, pos);
                    recvBuffer = recvBuffer.substr(pos + 2); // Remove processed message + delimiter

                    if (message.empty()) continue;

                    // Try Base64-decode then DES-decrypt
                    try {
                        string rawCiphertext = base64Decode(message);
                        if (rawCiphertext.empty()) {
                            // Not encrypted data - display as plaintext
                            cout << message << flush;
                            continue;
                        }
                        string decrypted = desDecryptString(rawCiphertext, desKey);
                        if (!decrypted.empty()) {
                            // Check for DES key confirmation (after decryption)
                            if (decrypted.find("[DESKEY_OK]") != string::npos) {
                                cout << "Server confirmed DES key receipt" << endl;
                                continue;
                            }
                            cout << decrypted << flush;
                        } else {
                            // Decryption failed, show as plaintext
                            cout << message << flush;
                        }
                    } catch (const exception& e) {
                        cout << "[DEBUG] Decryption exception: " << e.what() << endl;
                        // Show raw data as plaintext
                        cout << message << flush;
                    }
                }
            }
            else if (bytes_received == 0) {
                cout << "\nServer disconnected." << endl;
                connected = false;
                break;
            }
            else if (errno != EAGAIN && errno != EWOULDBLOCK) {
                cout << "\nReceive error: " << strerror(errno) << endl;
                connected = false;
                break;
            }
        }

        this_thread::sleep_for(chrono::milliseconds(10));
    }
}

int main() {
    // Create socket
    client_socket = socket(AF_INET, SOCK_STREAM, 0);
    if (client_socket == -1) {
        cout << "socket creation failed: " << strerror(errno) << endl;
        return 1;
    }

    sockaddr_in server_addr;
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(8080);

    if (inet_pton(AF_INET, "127.0.0.1", &server_addr.sin_addr) != 1) {
        cout << "Invalid IP address" << endl;
        close(client_socket);
        return 1;
    }

    if (connect(client_socket, (sockaddr*)&server_addr, sizeof(server_addr)) == -1) {
        cout << "Failed to connect: " << strerror(errno) << endl;
        close(client_socket);
        return 1;
    }

    cout << "Connected to server!" << endl;
    setNonBlocking(client_socket);

    // Receive public key
    if (!receivePublicKey()) {
        close(client_socket);
        return 1;
    }

    // Generate DES key
    desKey = generateRandomKey();
    cout << "Generated DES key: " << desKey << endl;

    ofstream keyFile("client_des.key");
    if (keyFile.is_open()) {
        keyFile << desKey;
        keyFile.close();
    }

    // Send DES key
    if (!sendDESKey("public.key")) {
        close(client_socket);
        return 1;
    }

    // Start receive thread
    thread receiver(receiveFunction);

    // Give receive thread time to start and get DESKEY_OK
    this_thread::sleep_for(chrono::milliseconds(200));

    // Enter nickname
    cout << "Enter your nickname: ";
    string client_name;
    getline(cin, client_name);

    if (client_name.empty()) {
        auto now = chrono::system_clock::now();
        auto timestamp_s = chrono::duration_cast<chrono::seconds>(now.time_since_epoch());
        client_name = to_string(timestamp_s.count());
    }

    // Send nickname: DES-encrypt, then Base64-encode, then append \r\n
    string nickname_msg = client_name + "\r\n";
    string encryptedNickname = desEncryptString(nickname_msg, desKey);
    string encodedNickname = base64Encode(encryptedNickname) + "\r\n";
    send(client_socket, encodedNickname.c_str(), encodedNickname.length(), 0);

    cout << "========================================" << endl;
    cout << "Chat started! Type /quit to exit" << endl;
    cout << "========================================" << endl;

    // Main loop: send messages
    string message;
    while (connected) {
        getline(cin, message);

        if (!connected) break;

        if (message == "/quit") {
            connected = false;
            break;
        }

        if (message.empty()) continue;

        // DES-encrypt, then Base64-encode, then append \r\n for framing
        message += "\r\n";
        string encryptedMsg = desEncryptString(message, desKey);
        string encodedMsg = base64Encode(encryptedMsg) + "\r\n";

        if (send(client_socket, encodedMsg.c_str(), encodedMsg.length(), 0) == -1) {
            cout << "Failed to send: " << strerror(errno) << endl;
            connected = false;
            break;
        }
    }

    if (receiver.joinable()) {
        receiver.join();
    }

    close(client_socket);
    cout << "Client exited" << endl;

    return 0;
}
