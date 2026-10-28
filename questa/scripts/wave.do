# File → Save Format writes ../wave.do (questa cwd). run.ps1 loads that.
do [file normalize [file join [file dirname [info script]] .. wave.do]]
