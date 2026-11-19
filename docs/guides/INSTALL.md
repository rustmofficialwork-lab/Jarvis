# JARVIS: download karo aur use karo

Windows installer GitHub Actions automatically banata hai. App install karne ke liye source ZIP ko repository mein upload karne ya code compile karne ki zaroorat nahi hai.

## Installer download karo

1. Repository ka **Actions** tab kholo: https://github.com/rustmofficialwork-lab/Jarvis/actions
2. Sabse naya **JARVIS Project Checks and Windows Build** run kholo.
3. Run ke **completed** hone aur green **Success** result aane ka wait karo. Installer build fail ya in-progress ho to download ko ready mat samjho.
4. **Artifacts** section se `JARVIS-Windows-Installer-x64` download karo. Ya **Releases** mein **JARVIS Latest Windows Build** release se `JARVIS-Setup-x64.exe` download karo, agar release publish hui ho.
5. Agar aapne `main` branch mein code change push kiya hai, to us push ke baad bana hua latest run hi check karo. Zaroorat par Actions workflow ke **Run workflow** option se build manually start kiya ja sakta hai.

## Install

1. Downloaded ZIP artifact ko extract karo (agar artifact ZIP hai), phir `JARVIS-Setup-x64.exe` chalao.
2. Installer mein **Install offline AI now** select karne par Ollama install hota hai. Agar build ke saath `offline-ai-bundle` ship hua hai, to Qwen3.5 4B local bundle se register hota hai; warna Ollama registry se lagbhag 3.3–4.0 GB model download hota hai. Isse local Qwen3.5 4B setup hota hai. General AI chat online aur offline dono mein isi ek local model se chalega; AI API key ya cloud AI backend ki zaroorat nahi. Live web search aur internet-only features ke liye internet connection chahiye.
3. App abhi code-signed nahi hai, isliye Windows SmartScreen warning dikha sakta hai. Publisher verify kiye bina kisi unexpected installer ko run mat karo.
4. JARVIS kholo. Typing se chat use kar sakte ho. Try: `good morning jarvis`, `notepad kholo aur phir calculator kholo`, `brain check`.

## Voice setup

Voice ke liye app ke andar **Set up wake word** aur **owner voice** ka guided setup follow karo. Wake-word model ko license ke kaaran installer mein bundle nahi kiya gaya hai; setup ke waqt publisher ki license terms review karo. Owner voice profile aapki apni awaaz se locally enroll hoti hai.
