from pathlib import Path
import gzip, hashlib, json, shutil, subprocess

WORK = Path(__file__).resolve().parent
OUT = WORK.parent / 'outputs' / 'Shrek2VideoPatch'
MOVIES = WORK / 'widescreen' / 'movies'
SOURCE = OUT / 'Source'

# Keep a copy for the version-upgrade regression before replacing the build.
previous = WORK / 'widescreen' / 'movies' / 'D3DDrv.previous-1.2.dll'
if not previous.exists():
    old = Path('E:/Shrek 2/System/D3DDrv.dll').read_bytes()
    assert hashlib.sha256(old).hexdigest() == 'fb879caf403b7dc4779da228edb54f746d4104ea333b39ac226a280e3b96023c'
    previous.write_bytes(old)
shutil.copy2(MOVIES / 'D3DDrv.movies.dll', WORK / 'widescreen/final/System/D3DDrv.dll')
subprocess.run(['python', str(WORK / 'package_patch.py')], check=True, capture_output=True)
compiler = Path('C:/Windows/Microsoft.NET/Framework/v4.0.30319/csc.exe')
exe = WORK / 'Shrek2VideoPatch-1.3.exe'
subprocess.run([str(compiler), '/nologo', '/target:winexe', '/out:' + str(exe),
                '/resource:' + str(WORK / 'patch.json.gz') + ',patch.json.gz',
                '/reference:System.Web.Extensions.dll', '/reference:System.Windows.Forms.dll',
                '/reference:System.Drawing.dll', str(WORK / 'PatchInstaller.cs')], check=True)
shutil.copy2(exe, OUT / 'Shrek2VideoPatch.exe')
for name in ['PatchInstaller.cs', 'patch.json.gz', 'package_patch.py']:
    shutil.copy2(WORK / name, SOURCE / name)

movie_source = SOURCE / 'Widescreen/Movies'
for name in ['patch_movies.py', 'verify_movies.py', 'verify_decoder_scaler.py',
             'movie-evidence.json', 'movie-emulation.json', 'movie-fit-code.asm',
             'decoder-scaler-evidence.json']:
    shutil.copy2(MOVIES / name, movie_source / name)
decoder_source = movie_source / 'decoder-integration'
decoder_source.mkdir(exist_ok=True)
for name in ['DecodeContract.cs', 'decoder-contract.json', 'colour-evidence.json']:
    shutil.copy2(MOVIES / 'decoder-integration' / name, decoder_source / name)
shutil.copy2(MOVIES / 'decoder-scaler-FGMcommercial1024-1280x720.png',
             OUT / 'Проверка ролика 1280x720.png')

manifest = json.loads(gzip.decompress((WORK / 'patch.json.gz').read_bytes()))
files = [{k: f[k] for k in ['Name', 'OriginalHash', 'PatchedHash']} for f in manifest['Files']]
verification = json.loads((SOURCE / 'verification.json').read_text(encoding='utf-8'))
verification.update(version='1.3', files=files, installed_to=None,
                    upgrade_repeat_restore_seven_files='pending',
                    actual_native_bink_copy_cases=8,
                    old_movie_mapping_overwrite_reproduced=True,
                    scaler_with_actual_decoded_frames=5,
                    runtime_gameplay_verified=False,
                    vsync_crash_before_apply_confirmed_by_user=True,
                    independent_vsync_crash_root_cause_proven=False)
(SOURCE / 'verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
build = json.loads((SOURCE / 'build-report.json').read_text(encoding='utf-8'))
build.update(version='1.3', final_files=files)
for item in ['Widescreen/Movies/decoder-integration/decoder-contract.json',
             'Widescreen/Movies/decoder-scaler-evidence.json']:
    if item not in build['new_stages']:
        build['new_stages'].append(item)
(SOURCE / 'build-report.json').write_text(json.dumps(build, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

readme = (OUT / 'README.txt').read_text(encoding='utf-8')
readme = readme.replace('Shrek 2 — единый патч 1.2', 'Shrek 2 — единый патч 1.3')
start = readme.index('Для версии 1.2 прошли')
end = readme.index('Машинный код коррекции камеры', start)
readme = readme[:start] + '''Для широкого экрана прошли 225 сценариев HUD/субтитров/индикаторов, 60 проверок
геометрии и шрифтов GUI, 80 вариантов выбора ролика, 7 синтетических полных
проверок пикселей видеоскейлера и 24 проверки его прямоугольника.
В версии 1.3 проверен настоящий установленный Bink-декодер в 32-битном процессе:
4 ролика × 2 формата кадра, включая защитные байты и заполнение строк.
Ошибка версии 1.2 воспроизведена отдельно: перепутанные 16/32-битные форматы
повреждали изображение и перезаписывали память за границей буфера.
Исправленный скейлер проверен на 5 кадрах этого декодера до 2560×1440.
Ранее декодер в тестах был заменён заглушкой с той же неверной таблицей форматов;
те проверки не подтверждали его настоящий контракт.
''' + readme[end:]
readme = readme.replace('после патча 1.2', 'после патча 1.3')
intro = '''ИСПРАВЛЕНИЕ 1.3
Исправлены полосы, неверные цвета и частичный вывод Bink-роликов из версии 1.2.
Устранён подтверждённый выход декодера за границу временного буфера.
При выборе VSync «Выкл.» зарегистрирован вылет в callback выпадающего списка
до Apply/SetRes. Исправление памяти может устранить такой последующий сбой,
но причинная связь именно с этим вылетом пока не доказана живым прогоном.
Все предыдущие функции единого патча сохранены. Обновление устанавливается
поверх версии 1.2 с использованием существующей исходной резервной копии.

'''
if 'ИСПРАВЛЕНИЕ 1.3' not in readme:
    readme = readme.replace('Добавлено в Настройки → Видео:', intro + 'Добавлено в Настройки → Видео:')
(OUT / 'README.txt').write_text(readme, encoding='utf-8')

audit = (OUT / 'Аудит кода.md').read_text(encoding='utf-8')
start = audit.index('Версия 1.2 проверена 225 сценариями')
end = audit.index('\n\nЦвет остаётся', start)
audit = audit[:start] + '''Версия 1.3 сохраняет проверки HUD, GUI и выбора качества роликов. Исправлена
ошибка моего видеоскейлера версии 1.2: `D3DFMT_X8R8G8B8=22` требует 4 байта
на пиксель и Bink-флаг `0x80000005`, а `D3DFMT_R5G6B5=23` — 2 байта и флаг
`0x8000000A`. Прежний тест повторял неверную таблицу в заглушке декодера и
ошибочно проходил. Новая проверка исполняет настоящий `binkw32.dll` в x86:
8 корректных копирований четырёх кадров не нарушают границы и padding строк;
отдельный безопасно размещённый отрицательный контроль старой таблицы
подтверждает перезапись за границей логического буфера. Цвета RGB565 и BGRX32
согласуются в пределах квантования [7,3,7]. Пять кадров настоящего декодера
затем прошли полный пиксельный тест вставленного x86-скейлера до 2560×1440.
Это офлайн-проверка декодера и эмуляция скейлера, а не запуск игры.

Журнал последнего пользовательского вылета VSync заканчивается в
`GUIComboBox.TextChanged → UObject::execDelegateFunction` до нового `SetRes`.
Пользователь подтвердил вылет сразу при выборе «Выкл.». Сам скриптовый
переключатель лишь показывает «Применить»; `UseVSync=False` записывается
позднее при Apply. Повреждение heap роликами подтверждено отдельно;
причинная связь с этим callback-сбоем пока остаётся гипотезой. Живая проверка
после исправления 1.3 ещё не выполнена. Скейлер использует ближайший пиксель;
native-путь относится к Direct3D, а не Pixo или MovieTexture на 3D-объектах.''' + audit[end:]
(OUT / 'Аудит кода.md').write_text(audit, encoding='utf-8')
print(json.dumps({'version': manifest['Version'], 'exe_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(), 'files': files}, indent=2))
