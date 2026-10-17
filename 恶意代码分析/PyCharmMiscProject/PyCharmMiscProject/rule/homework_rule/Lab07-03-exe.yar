rule Lab07_03_exe {
   meta:
      description = " - file Lab07-03.dll"
      author = "Luhaozhhhe"
      date = "2024-10-27"

   strings:
      $string1 = "kerne132.dll" 
      $string2 = "Lab07-03.dll"


   condition:
       filesize < 50KB and uint16(0) == 0x5A4D and uint16(uint16(0x3C)) == 0x00004550 and all of them
}