rule BossDaMajor {    
   strings:
        $s1 = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run"
        $s2 = "kernel32.dll"
        $s3 = "user32.dll"
        $s4 = "advapi32.dll"
        $s5 = "shell32.dll"
        $s6 = "CreateProcessA"
        $s7 = "CreateFileA"
        $s8 = "RegSetValueExA"
        $s9 = "InternetOpenA"
        $s10 = "GetSystemDirectoryA"
        $s11 = "WriteFile"
        $s12 = "ReadFile"
    
    condition:
        any of them
}