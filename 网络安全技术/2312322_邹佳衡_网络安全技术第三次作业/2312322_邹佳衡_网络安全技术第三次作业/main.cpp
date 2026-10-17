// main.cpp
// MD5 — Command-Line Entry Point

#include "MD5.h"
#include <iostream>
#include <string>

using namespace std;

int main(int argc, char *argv[]) {
    if (argc < 2) {
        md5PrintHelp();
        return 1;
    }

    string option = argv[1];

    if (option == "-h") {
        md5PrintHelp();
    }
    else if (option == "-t") {
        md5PrintTestCases();
    }
    else if (option == "-c") {
        if (argc < 3) {
            cerr << "Error: Missing file path for -c option" << endl;
            return 1;
        }
        md5ComputeFile(argv[2]);
    }
    else if (option == "-v") {
        if (argc < 3) {
            cerr << "Error: Missing file path for -v option" << endl;
            return 1;
        }
        md5ValidateByManualInput(argv[2]);
    }
    else if (option == "-f") {
        if (argc < 4) {
            cerr << "Error: Missing file path(s) for -f option" << endl;
            return 1;
        }
        md5ValidateByFile(argv[2], argv[3]);
    }
    else {
        cerr << "Error: Unknown option \"" << option << "\"" << endl;
        md5PrintHelp();
        return 1;
    }

    return 0;
}
