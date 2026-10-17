rule yhzll {    
     strings:
        // 测试WannaCry相关特征
        $s1 = "WanaDecrypt0r" nocase
        $s2 = "WannaDecryptor" nocase
        $s3 = "WannaCry" nocase
        $s4 = "wnry" nocase
        $s5 = "mssecsvc2.0" nocase
        $s6 = "Ooops, your files have been encrypted!" nocase
        $s7 = "tasksche.exe" nocase
        $s8 = "@Please_Read_Me@.txt" nocase
        $s9 = "Bitcoin" nocase
        $s10 = "What happened to my computer?" nocase
        
            
    condition:
        any of them
}