using System;
using System.IO;
using System.IO.Compression;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Security.Cryptography;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using System.Drawing;

class FilePatch {
    public string Name {get;set;}
    public string OriginalHash {get;set;}
    public string PatchedHash {get;set;}
    public string[] PriorPatchedHashes {get;set;}
    public Hunk[] Hunks {get;set;}
}
class Hunk {public int Offset {get;set;} public string Before {get;set;} public string After {get;set;}}
class Manifest {public string Version {get;set;} public FilePatch[] Files {get;set;}}
class Installer {
    static Manifest manifest;
    static string Hash(byte[] data) {using(var s=SHA256.Create())return BitConverter.ToString(s.ComputeHash(data)).Replace("-", "").ToLowerInvariant();}
    static Manifest Load() {
        using(var r=typeof(Installer).Assembly.GetManifestResourceStream("patch.json.gz"))
        using(var z=new GZipStream(r,CompressionMode.Decompress))
        using(var sr=new StreamReader(z,Encoding.UTF8))
            return new JavaScriptSerializer {MaxJsonLength=8000000}.Deserialize<Manifest>(sr.ReadToEnd());
    }
    static byte[] Apply(byte[] original, FilePatch p) {
        string hash=Hash(original);
        if(hash==p.PatchedHash)return original;
        if(hash!=p.OriginalHash)throw new Exception("Другая версия файла "+p.Name+". Файлы игры не изменены.");
        using(var output=new MemoryStream()) {
            int last=0;
            foreach(var h in p.Hunks) {
                byte[] before=Convert.FromBase64String(h.Before), after=Convert.FromBase64String(h.After);
                if(h.Offset<last||h.Offset+before.Length>original.Length)throw new Exception("Повреждённые данные патча.");
                if(!original.Skip(h.Offset).Take(before.Length).SequenceEqual(before))throw new Exception("Файл не прошёл проверку: "+p.Name);
                output.Write(original,last,h.Offset-last);output.Write(after,0,after.Length);last=h.Offset+before.Length;
            }
            output.Write(original,last,original.Length-last);
            byte[] result=output.ToArray();
            if(Hash(result)!=p.PatchedHash)throw new Exception("Не совпала контрольная сумма: "+p.Name);
            return result;
        }
    }
    static void CheckStopped(string system) {
        foreach(var process in System.Diagnostics.Process.GetProcessesByName("game")) {
            try {if(String.Equals(Path.GetDirectoryName(process.MainModule.FileName),system,StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Закройте Shrek 2 и повторите установку. Игра сейчас запущена.");}
            catch(InvalidOperationException){throw;}
            catch {throw new Exception("Обнаружен запущенный game.exe. Закройте игру и повторите установку.");}
        }
    }
    static readonly string[][] DevKeys={new[]{"F9","ToggleDebugMode"},new[]{"F10","ShowDevMenu"}};
    static string DefaultProfile() {return Path.Combine(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),"Shrek 2"),"User.ini");}
    static int FindKey(List<string> lines,string key) {
        bool input=false;
        for(int i=0;i<lines.Count;i++) {
            string t=lines[i].Trim();
            if(t.StartsWith("["))input=String.Equals(t,"[Engine.Input]",StringComparison.OrdinalIgnoreCase);
            else if(input&&lines[i].StartsWith(key+"=",StringComparison.OrdinalIgnoreCase))return i;
        }
        return -1;
    }
    static string DevMenu(string backup,string profile,bool enable) {
        string state=Path.Combine(backup,"devmenu.txt");
        if(!File.Exists(profile)) {
            if(enable)return "\n\nМеню разработчиков не подключено: не найден "+profile+". Запустите игру один раз и повторите установку.";
            return "";
        }
        byte[] raw=File.ReadAllBytes(profile);
        string text=Encoding.Default.GetString(raw);
        string nl=text.Contains("\r\n")?"\r\n":"\n";
        var lines=text.Split(new[]{nl},StringSplitOptions.None).ToList();
        var saved=new Dictionary<string,string>();
        if(File.Exists(state))foreach(var l in File.ReadAllLines(state,Encoding.UTF8)){int k=l.IndexOf('=');if(k>0)saved[l.Substring(0,k)]=l.Substring(k+1);}
        var notes=new List<string>();
        bool changed=false;
        if(enable) {
            foreach(var d in DevKeys) {
                int i=FindKey(lines,d[0]);
                if(i<0){notes.Add(d[0]+": нет строки в [Engine.Input]");continue;}
                string cur=lines[i].Substring(d[0].Length+1);
                if(cur.Trim()==d[1]){if(!saved.ContainsKey(d[0]))saved[d[0]]=" ";continue;}
                if(cur.Trim()!=""){notes.Add(d[0]+" уже занята командой «"+cur.Trim()+"» и не изменена");continue;}
                if(!saved.ContainsKey(d[0]))saved[d[0]]=cur;
                lines[i]=d[0]+"="+d[1];changed=true;
            }
            File.WriteAllLines(state,saved.Select(x=>x.Key+"="+x.Value).ToArray(),Encoding.UTF8);
        } else {
            if(!File.Exists(state))return "";
            foreach(var d in DevKeys) {
                int i=FindKey(lines,d[0]);
                if(i<0||!saved.ContainsKey(d[0]))continue;
                if(lines[i].Substring(d[0].Length+1).Trim()==d[1]){lines[i]=d[0]+"="+saved[d[0]];changed=true;}
            }
        }
        if(changed) {
            string bak=Path.Combine(backup,"User.ini.before-devmenu");
            if(!File.Exists(bak))File.WriteAllBytes(bak,raw);
            File.WriteAllBytes(profile,Encoding.Default.GetBytes(String.Join(nl,lines.ToArray())));
        }
        if(!enable){File.Delete(state);return "\n\nКлавиши меню разработчиков F9/F10 убраны.";}
        string msg="\n\nМеню разработчиков: F9 — включить режим разработчика, F10 — открыть Dev Menu.";
        return notes.Count>0?msg+"\n"+String.Join("\n",notes.ToArray()):msg;
    }
    static string Saved(string backup,string name) {return Path.Combine(backup,name.StartsWith("..\\")?name.Substring(3):name);}
    static string Run(string path, bool restore, bool check, bool devmenu, string profile) {
        string system=Path.GetFullPath(path).TrimEnd(Path.DirectorySeparatorChar);
        if(!Directory.Exists(system))throw new Exception("Не найдена папка System: "+system);
        string backup=Path.Combine(system,"Shrek2VideoPatchBackup");
        var files=new Dictionary<string,byte[]>();
        foreach(var p in manifest.Files) {
            string target=Path.Combine(system,p.Name);
            if(restore) {
                string saved=Saved(backup,p.Name);
                if(!File.Exists(saved)) {
                    if(File.Exists(target)&&Hash(File.ReadAllBytes(target))==p.OriginalHash)continue;
                    throw new Exception("Не найдена резервная копия: "+p.Name);
                }
                byte[] original=File.ReadAllBytes(saved);
                if(Hash(original)!=p.OriginalHash)throw new Exception("Резервная копия не прошла проверку: "+p.Name);
                byte[] current=File.ReadAllBytes(target);
                if(Hash(current)!=p.PatchedHash&&Hash(current)!=p.OriginalHash&&!(p.PriorPatchedHashes??new string[0]).Contains(Hash(current)))throw new Exception("Файл изменён после установки: "+p.Name);
                files.Add(target,original);
            } else {
                if(!File.Exists(target))throw new Exception("Не найден файл игры: "+p.Name);
                byte[] input=File.ReadAllBytes(target);
                if((p.PriorPatchedHashes??new string[0]).Contains(Hash(input))) {
                    string saved=Saved(backup,p.Name);
                    if(!File.Exists(saved)||Hash(File.ReadAllBytes(saved))!=p.OriginalHash)
                        throw new Exception("Для обновления прежнего патча нужна исходная резервная копия: "+p.Name);
                    input=File.ReadAllBytes(saved);
                }
                files.Add(target,Apply(input,p));
            }
        }
        if(check)return "Проверка успешна. Все файлы подходят, контрольные суммы результата совпадают.";
        CheckStopped(system);
        Directory.CreateDirectory(backup);
        foreach(var p in manifest.Files) {
            string target=Path.Combine(system,p.Name),saved=Saved(backup,p.Name);
            if(!restore) {
                if(!File.Exists(saved)) {
                    byte[] bytes=File.ReadAllBytes(target);
                    if(Hash(bytes)!=p.OriginalHash)throw new Exception("Нет оригинала для резервной копии: "+p.Name);
                    Directory.CreateDirectory(Path.GetDirectoryName(saved));
                    File.WriteAllBytes(saved,bytes);
                }
                if(Hash(File.ReadAllBytes(saved))!=p.OriginalHash)throw new Exception("Другая резервная копия: "+p.Name);
            }
        }
        var prior=new Dictionary<string,byte[]>();
        try {
            foreach(var f in files) {
                if(File.ReadAllBytes(f.Key).SequenceEqual(f.Value))continue;
                prior.Add(f.Key,File.ReadAllBytes(f.Key));
                File.WriteAllBytes(f.Key,f.Value);
            }
        } catch {
            foreach(var f in prior) {try{File.WriteAllBytes(f.Key,f.Value);}catch{}}
            throw;
        }
        File.WriteAllText(Path.Combine(backup,"version.txt"),manifest.Version+Environment.NewLine,Encoding.UTF8);
        string dev=DevMenu(backup,profile,!restore&&devmenu);
        return (restore?"Оригинальные файлы восстановлены.":"Единый патч установлен.\n\nHUD, меню, субтитры и видеоролики сохраняют пропорции на широком экране. Доступны разрешения до 2560×1440, оконный режим, VSync и Alt+F4. Заставки с логотипами пропускаются, книга главного меню открывается быстрее. Исправлена лестница в тюрьме (уровень с Котом), на которую нельзя было забраться при высоком FPS. Предыдущие исправления сохранены.\nОригиналы находятся в Shrek2VideoPatchBackup.")+dev;
    }
    [STAThread]
    static int Main(string[] args) {
        manifest=Load();
        string system=@"E:\Shrek 2\System",report=null,profile=DefaultProfile();bool restore=false,check=false,devmenu=false,cli=args.Length>0;
        for(int i=0;i<args.Length;i++) {
            if(args[i]=="--system")system=args[++i];
            else if(args[i]=="--devmenu")devmenu=true;
            else if(args[i]=="--profile")profile=args[++i];
            else if(args[i]=="--restore")restore=true;
            else if(args[i]=="--check")check=true;
            else if(args[i]=="--report")report=args[++i];
            else throw new ArgumentException("Unknown argument: "+args[i]);
        }
        if(cli) {
            try {string result=Run(system,restore,check,devmenu,profile);if(report!=null)File.WriteAllText(report,result,Encoding.UTF8);return 0;}
            catch(Exception e){if(report!=null)File.WriteAllText(report,e.ToString(),Encoding.UTF8);return 1;}
        }
        Application.EnableVisualStyles();
        var form=new Form {Text="Shrek 2 — единый патч 1.7",ClientSize=new Size(620,280),FormBorderStyle=FormBorderStyle.FixedDialog,MaximizeBox=false,StartPosition=FormStartPosition.CenterScreen};
        var info=new Label{Text="HUD и видео 16:9 · До 2560×1440 · Окно · VSync · Alt+F4 · Без заставок\n\nПапка System установленной игры:",AutoSize=true,Location=new Point(20,20)};
        var input=new TextBox{Text=system,Location=new Point(20,85),Size=new Size(470,25)};
        var browse=new Button{Text="Обзор…",Location=new Point(500,83),Size=new Size(100,28)};
        browse.Click+=(s,e)=>{using(var dialog=new FolderBrowserDialog{Description="Выберите папку System игры Shrek 2",SelectedPath=input.Text})if(dialog.ShowDialog()==DialogResult.OK)input.Text=dialog.SelectedPath;};
        var dev=new CheckBox{Text="Разблокировать меню разработчиков (F9 — режим разработчика, F10 — Dev Menu)",AutoSize=true,Location=new Point(20,122),
            Checked=File.Exists(Path.Combine(Path.Combine(system,"Shrek2VideoPatchBackup"),"devmenu.txt"))};
        var install=new Button{Text="Установить патч",Location=new Point(20,155),Size=new Size(180,38)};
        var rollback=new Button{Text="Восстановить оригинал",Location=new Point(215,155),Size=new Size(190,38)};
        var note=new Label{Text="Перед установкой закройте игру. Резервная копия создаётся автоматически.\nСохранения не изменяются. Настройки управления меняются только галочкой выше\n(строки F9/F10 в Документы\\Shrek 2\\User.ini, откат — снять галочку или «Восстановить оригинал»).",AutoSize=true,Location=new Point(20,210)};
        Action<bool> run=(undo)=>{try{MessageBox.Show(form,Run(input.Text,undo,false,dev.Checked,profile),"Shrek 2",MessageBoxButtons.OK,MessageBoxIcon.Information);}catch(Exception ex){MessageBox.Show(form,ex.Message,"Не удалось применить патч",MessageBoxButtons.OK,MessageBoxIcon.Error);}};
        install.Click+=(s,e)=>run(false);rollback.Click+=(s,e)=>run(true);
        form.Controls.AddRange(new Control[]{info,input,browse,dev,install,rollback,note});Application.Run(form);return 0;
    }
}
