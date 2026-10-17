rule Lab11_01_exe {
   meta:
      description = " - file Lab11-01.exe"
      author = "Luhaozhhhe"
      date = "2024-11-18"

   strings:
      $string1 = "msgina32.dll" 
      

   condition:
      all of them
}