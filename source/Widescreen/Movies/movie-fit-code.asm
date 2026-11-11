10001800  pushal   
10001801  sub      esp, 0x40
10001804  mov      ebp, esp
10001806  call     0x1000180b
1000180B  pop      ebx
1000180C  sub      ebx, 0x180b
10001812  mov      esi, dword ptr [ebp + 0x44]
10001815  mov      esi, dword ptr [esi + 0x10]
10001818  mov      dword ptr [ebp + 0x34], esi
1000181B  mov      eax, dword ptr [esi]
1000181D  mov      edx, dword ptr [esi + 4]
10001820  test     eax, eax
10001822  jle      0x100019ec
10001828  test     edx, edx
1000182A  jle      0x100019ec
10001830  cmp      eax, 0x4000
10001835  jg       0x100019ec
1000183B  cmp      edx, 0x4000
10001841  jg       0x100019ec
10001847  mov      dword ptr [ebp], eax
1000184A  mov      dword ptr [ebp + 4], edx
1000184D  mov      ecx, 4
10001852  cmp      dword ptr [ebp + 0x84], 0x16
10001859  je       0x1000186d
1000185B  cmp      dword ptr [ebp + 0x84], 0x17
10001862  jne      0x100019ec
10001868  mov      ecx, 2
1000186D  mov      dword ptr [ebp + 8], ecx
10001870  imul     eax, ecx
10001873  mov      dword ptr [ebp + 0x28], eax
10001876  imul     eax, edx
10001879  push     eax
1000187A  call     dword ptr [ebx + 0x12ee24]
10001880  add      esp, 4
10001883  test     eax, eax
10001885  je       0x100019ec
1000188B  mov      dword ptr [ebp + 0xc], eax
1000188E  mov      ecx, dword ptr [ebp + 0x9c]
10001894  mov      edx, dword ptr [ebp + 0xa0]
1000189A  test     ecx, ecx
1000189C  jle      0x100019e0
100018A2  test     edx, edx
100018A4  jle      0x100019e0
100018AA  cmp      ecx, 0x4000
100018B0  jg       0x100019e0
100018B6  cmp      edx, 0x4000
100018BC  jg       0x100019e0
100018C2  mov      eax, ecx
100018C4  imul     eax, dword ptr [ebp + 4]
100018C8  imul     edx, dword ptr [ebp]
100018CC  cmp      eax, edx
100018CE  jle      0x100018e7
100018D0  mov      eax, dword ptr [ebp + 0xa0]
100018D6  mov      dword ptr [ebp + 0x14], eax
100018D9  imul     eax, dword ptr [ebp]
100018DD  xor      edx, edx
100018DF  div      dword ptr [ebp + 4]
100018E2  mov      dword ptr [ebp + 0x10], eax
100018E5  jmp      0x100018f8
100018E7  mov      dword ptr [ebp + 0x10], ecx
100018EA  mov      eax, ecx
100018EC  imul     eax, dword ptr [ebp + 4]
100018F0  xor      edx, edx
100018F2  div      dword ptr [ebp]
100018F5  mov      dword ptr [ebp + 0x14], eax
100018F8  cmp      dword ptr [ebp + 0x10], 1
100018FC  jge      0x10001905
100018FE  mov      dword ptr [ebp + 0x10], 1
10001905  cmp      dword ptr [ebp + 0x14], 1
10001909  jge      0x10001912
1000190B  mov      dword ptr [ebp + 0x14], 1
10001912  mov      eax, dword ptr [ebp + 0x9c]
10001918  sub      eax, dword ptr [ebp + 0x10]
1000191B  shr      eax, 1
1000191D  mov      dword ptr [ebp + 0x18], eax
10001920  imul     eax, dword ptr [ebp + 8]
10001924  mov      ecx, dword ptr [ebp + 0xa0]
1000192A  sub      ecx, dword ptr [ebp + 0x14]
1000192D  shr      ecx, 1
1000192F  mov      dword ptr [ebp + 0x1c], ecx
10001932  mov      edx, dword ptr [ebp + 0x70]
10001935  mov      dword ptr [ebp + 0x24], edx
10001938  imul     ecx, edx
1000193B  add      eax, ecx
1000193D  add      eax, dword ptr [ebp + 0xbc]
10001943  mov      dword ptr [ebp + 0x20], eax
10001946  mov      eax, 0x80000005
1000194B  cmp      dword ptr [ebp + 8], 4
1000194F  je       0x10001956
10001951  mov      eax, 0x8000000a
10001956  push     eax
10001957  push     0
10001959  push     0
1000195B  push     dword ptr [ebp + 4]
1000195E  push     dword ptr [ebp + 0x28]
10001961  push     dword ptr [ebp + 0xc]
10001964  push     dword ptr [ebp + 0x34]
10001967  call     dword ptr [ebx + 0x12ef28]
1000196D  mov      dword ptr [ebp + 0x3c], 0
10001974  mov      eax, dword ptr [ebp + 0x3c]
10001977  imul     eax, dword ptr [ebp + 4]
1000197B  xor      edx, edx
1000197D  div      dword ptr [ebp + 0x14]
10001980  imul     eax, dword ptr [ebp + 0x28]
10001984  add      eax, dword ptr [ebp + 0xc]
10001987  mov      esi, eax
10001989  mov      edi, dword ptr [ebp + 0x20]
1000198C  mov      ecx, dword ptr [ebp + 0x10]
1000198F  xor      edx, edx
10001991  cmp      dword ptr [ebp + 8], 4
10001995  jne      0x100019b3
10001997  mov      eax, dword ptr [esi]
10001999  mov      dword ptr [edi], eax
1000199B  add      edi, 4
1000199E  add      edx, dword ptr [ebp]
100019A1  cmp      edx, dword ptr [ebp + 0x10]
100019A4  jb       0x100019ae
100019A6  sub      edx, dword ptr [ebp + 0x10]
100019A9  add      esi, 4
100019AC  jmp      0x100019a1
100019AE  dec      ecx
100019AF  jne      0x10001997
100019B1  jmp      0x100019cf
100019B3  mov      ax, word ptr [esi]
100019B6  mov      word ptr [edi], ax
100019B9  add      edi, 2
100019BC  add      edx, dword ptr [ebp]
100019BF  cmp      edx, dword ptr [ebp + 0x10]
100019C2  jb       0x100019cc
100019C4  sub      edx, dword ptr [ebp + 0x10]
100019C7  add      esi, 2
100019CA  jmp      0x100019bf
100019CC  dec      ecx
100019CD  jne      0x100019b3
100019CF  mov      eax, dword ptr [ebp + 0x24]
100019D2  add      dword ptr [ebp + 0x20], eax
100019D5  inc      dword ptr [ebp + 0x3c]
100019D8  mov      eax, dword ptr [ebp + 0x3c]
100019DB  cmp      eax, dword ptr [ebp + 0x14]
100019DE  jl       0x10001974
100019E0  push     dword ptr [ebp + 0xc]
100019E3  call     dword ptr [ebx + 0x12ee74]
100019E9  add      esp, 4
100019EC  mov      esp, ebp
100019EE  add      esp, 0x40
100019F1  popal    
100019F2  jmp      0x100244e7
