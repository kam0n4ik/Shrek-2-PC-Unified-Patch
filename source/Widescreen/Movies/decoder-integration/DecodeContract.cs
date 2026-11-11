using System;
using System.IO;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Web.Script.Serialization;
using System.Security.Cryptography;

class DecodeContract {
    const string DLL = @"E:\Shrek 2\System\binkw32.dll";
    [DllImport(DLL,EntryPoint="_BinkOpen@8",ExactSpelling=true,CallingConvention=CallingConvention.StdCall,CharSet=CharSet.Ansi)]
    static extern IntPtr BinkOpen([MarshalAs(UnmanagedType.LPStr)] string path, uint flags);
    [DllImport(DLL,EntryPoint="_BinkGetError@0",ExactSpelling=true,CallingConvention=CallingConvention.StdCall)]
    static extern IntPtr BinkGetError();
    [DllImport(DLL,EntryPoint="_BinkDoFrame@4",ExactSpelling=true,CallingConvention=CallingConvention.StdCall)]
    static extern int BinkDoFrame(IntPtr movie);
    [DllImport(DLL,EntryPoint="_BinkGoto@12",ExactSpelling=true,CallingConvention=CallingConvention.StdCall)]
    static extern void BinkGoto(IntPtr movie,uint frame,uint flags);
    [DllImport(DLL,EntryPoint="_BinkCopyToBuffer@28",ExactSpelling=true,CallingConvention=CallingConvention.StdCall)]
    static extern int BinkCopyToBuffer(IntPtr movie,IntPtr buffer,int pitch,uint height,uint x,uint y,uint flags);
    [DllImport(DLL,EntryPoint="_BinkClose@4",ExactSpelling=true,CallingConvention=CallingConvention.StdCall)]
    static extern void BinkClose(IntPtr movie);
    static string Hash(byte[] data) { using(var sha=SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(data)).Replace("-","").ToLowerInvariant(); }

    static Dictionary<string,object> Copy(IntPtr movie,int w,int h,int bpp,uint format,string prefix,string outdir,bool expectedFailure=false) {
        const int Guard=4096;
        int pitch=w*bpp+32;
        int logical=pitch*h;
        // Always reserve the larger 32-bit capacity, even for the 16-bit probe.
        // A wrong format contract can then be detected without writing off heap.
        int physical=(w*4+32)*h;
        int allocation=physical+2*Guard;
        IntPtr mem=Marshal.AllocHGlobal(allocation);
        try {
            byte[] initial=new byte[allocation]; for(int i=0;i<initial.Length;i++) initial[i]=0xCD;
            Marshal.Copy(initial,0,mem,initial.Length);
            IntPtr dest=IntPtr.Add(mem,Guard);
            uint flags=0x80000000u|format;
            int ret=BinkCopyToBuffer(movie,dest,pitch,(uint)h,0,0,flags);
            byte[] all=new byte[allocation];Marshal.Copy(mem,all,0,all.Length);
            bool before=true,afterLogical=true,afterPhysical=true,padding=true;
            for(int i=0;i<Guard;i++) if(all[i]!=0xCD)before=false;
            for(int i=Guard+logical;i<all.Length;i++) if(all[i]!=0xCD)afterLogical=false;
            for(int i=Guard+physical;i<all.Length;i++) if(all[i]!=0xCD)afterPhysical=false;
            for(int y=0;y<h;y++) for(int i=w*bpp;i<pitch;i++) if(all[Guard+y*pitch+i]!=0xCD)padding=false;
            byte[] tight=new byte[w*h*bpp];
            for(int y=0;y<h;y++) Buffer.BlockCopy(all,Guard+y*pitch,tight,y*w*bpp,w*bpp);
            string file=prefix+"-flags"+format+"-"+(bpp*8)+"bit.raw";
            File.WriteAllBytes(Path.Combine(outdir,file),tight);
            var report=new Dictionary<string,object> {
                {"format_flags",String.Format("0x{0:X8}",flags)},{"bpp",bpp},{"width",w},{"height",h},
                {"pitch",pitch},{"logical_buffer_bytes",logical},{"physical_capacity_bytes",physical},
                {"tight_file",file},{"tight_bytes",tight.Length},{"tight_sha256",Hash(tight)},
                {"return_value",ret},{"guard_before",before},{"guard_after_logical",afterLogical},
                {"guard_after_physical",afterPhysical},{"row_padding_unchanged",padding},
                {"expected_logical_overwrite",expectedFailure}
            };
            if(expectedFailure) {
                // A controlled negative test of the old erroneous contract.
                // The larger reserved capacity prevents a real heap overrun.
                if(!before||!afterPhysical||afterLogical||padding)throw new Exception("Negative control did not produce the expected logical overrun: "+new JavaScriptSerializer().Serialize(report));
            } else if(!before||!afterLogical||!afterPhysical||!padding)throw new Exception("Decoder buffer bounds FAILED: "+new JavaScriptSerializer().Serialize(report));
            return report;
        } finally { Marshal.FreeHGlobal(mem); }
    }

    static int Main(string[] args) {
        string outdir=args.Length>0?Path.GetFullPath(args[0]):Environment.CurrentDirectory;
        Directory.CreateDirectory(outdir);
        var rows=new List<Dictionary<string,object>>();
        try {
            if(IntPtr.Size!=4)throw new Exception("Harness must run as x86");
            foreach(string filename in new[]{"FGMcommercial1024.bik","KWLogo1024.bik","ACTIVSN512.bik","DW_LOGO640.bik"}) {
                string path=Path.Combine(@"E:\Shrek 2\Movies",filename);
                IntPtr movie=BinkOpen(path,0);
                if(movie==IntPtr.Zero)throw new Exception("BinkOpen: "+Marshal.PtrToStringAnsi(BinkGetError()));
                try {
                    int w=Marshal.ReadInt32(movie,0),h=Marshal.ReadInt32(movie,4);
                    uint frame=filename.StartsWith("FGM")?241u:filename.StartsWith("KW")?37u:20u;
                    BinkGoto(movie,frame,0);int decode=BinkDoFrame(movie);
                    string prefix=Path.GetFileNameWithoutExtension(filename)+"-frame"+frame;
                    var row=new Dictionary<string,object>{{"file",filename},{"frame",frame},{"width",w},{"height",h},{"do_frame_return",decode}};
                    row["copy32"]=Copy(movie,w,h,4,5,prefix,outdir);
                    row["copy16"]=Copy(movie,w,h,2,10,prefix,outdir);
                    if(filename.StartsWith("FGM"))row["negative_control_old_mapping"]=Copy(movie,w,h,2,5,"NEGATIVE-"+prefix,outdir,true);
                    rows.Add(row);
                    Console.WriteLine(filename+" "+w+"x"+h+" flags5=4bpp / flags10=2bpp: bounds passed");
                } finally { BinkClose(movie); }
            }
            var final=new Dictionary<string,object>{{"process_bits",IntPtr.Size*8},{"decoder_dll",DLL},{"decoder_sha256",Hash(File.ReadAllBytes(DLL))},{"open_flags",0},{"actual_native_decoder",true},{"cases",rows}};
            File.WriteAllText(Path.Combine(outdir,"decoder-contract.json"),new JavaScriptSerializer().Serialize(final));
            return 0;
        } catch(Exception e) { File.WriteAllText(Path.Combine(outdir,"decoder-error.txt"),e.ToString());Console.Error.WriteLine(e);return 1; }
    }
}
