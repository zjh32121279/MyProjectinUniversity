rule bug32 {
   strings:
        $s1 = "encrypt" nocase
        $s2 = "bitcoin" nocase
        $s3 = "decrypt" nocase
        $s4 = "payment" nocase
        $s5 = "recover" nocase
        $s6 = "Your files" nocase
        $s7 = "Send" nocase
        $s8 = "$300" nocase
        $s9 = "HELP_DECRYPT" nocase
        $s10 = "README" nocase
    
    condition:
        any of them
  }