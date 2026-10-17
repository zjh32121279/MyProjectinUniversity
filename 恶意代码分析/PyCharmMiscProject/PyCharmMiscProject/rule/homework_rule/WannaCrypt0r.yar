rule WannaCrypt0r {
        strings:
        // 唯一字符串特征
        $s1 = "WanaDecrypt0r" nocase ascii wide
        $s2 = "WannaDecryptor" nocase ascii wide
        $s3 = "TaskStart" fullword ascii
        $s4 = "TaskStart" fullword wide
        $s5 = "mssecsvc2.0" ascii
        $s6 = "wnry" ascii
        
        // 勒索信息相关
        $s7 = "Please read the \"@Please_Read_Me@.txt\""
        $s8 = "Your files are encrypted!" ascii
        
        // 资源段特征
        $s9 = "XIA" ascii  // 独特的资源名称
        
        // 十六进制特征 - 独特的代码序列
        $hex1 = { 55 8B EC 83 EC 10 53 56 57 8B 7D 08 8B 47 0C }
        $hex2 = { E8 ?? ?? ?? ?? 84 C0 74 ?? 8B 0D ?? ?? ?? ?? }

    condition:
        // 基础文件验证
        uint16(0) == 0x5A4D and        // PE文件标志
        filesize < 4000KB and          // 文件大小限制
        
        // 多特征组合检测
        (
            (2 of ($s1, $s2, $s5, $s6)) or          // 核心标识符
            ($s1 and $s5) or                        // WanaDecrypt0r + mssecsvc2.0
            ($s9 and filesize > 100KB) or           // 资源特征 + 大小
            (3 of ($s*)) or                         // 任意3个字符串
            (1 of ($hex*))                          // 代码特征
        )
}