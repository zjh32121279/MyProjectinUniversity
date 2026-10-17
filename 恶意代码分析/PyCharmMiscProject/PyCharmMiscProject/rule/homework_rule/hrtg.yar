rule hrtg {
     strings:
        // 最核心的系统特征
        $s1 = "SOFTWARE\\Microsoft\\Cryptography"
        $s2 = "crypt32.dll"
        $s3 = "advapi32.dll"
        $s4 = "kernel32.dll"
        $s5 = "CreateRemoteThread"
        
    condition:
        $s1 or $s2 or $s3 or $s4 or $s5
}