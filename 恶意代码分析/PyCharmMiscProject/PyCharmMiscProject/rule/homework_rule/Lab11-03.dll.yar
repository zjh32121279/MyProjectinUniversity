rule Lab11_03_dll {
   meta:
      description = " - file Lab11-03.dll"
      author = "Luhaozhhhe"
      date = "2024-11-18"

   strings:
      $string1 = "Lab1103dll.dll" wide ascii
      $string2 = "zzz69806582" wide ascii
      

   condition:
      all of them
}