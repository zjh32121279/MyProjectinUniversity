rule Lab07_03_dll {
   meta:
      description = " - file Lab07-03.dll"
      author = "Luhaozhhhe"
      date = "2024-10-27"

   strings:
      $string1 = "127.26.152.13" 
      $string2 = "_adjust_fdiv"


   condition:
       filesize < 200KB and uint16(0) == 0x5A4D and uint16(uint16(0x3C)) == 0x00004550 and all of them
}