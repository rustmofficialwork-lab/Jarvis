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
2. Installer mein **Install offline AI now** select karne par Ollama aur Llama 3.2 3B ka lagbhag 2 GB download hoga. Isse local offline AI setup hota hai; internet/cloud-only features offline available nahi honge.
3. App abhi code-signed nahi hai, isliye Windows SmartScreen warning dikha sakta hai. Publisher verify kiye bina kisi unexpected installer ko run mat karo.
4. JARVIS kholo. Typing se chat use kar sakte ho. Try: `good morning jarvis`, `notepad kholo aur phir calculator kholo`, `brain check`.

## Voice setup

Voice ke liye app ke andar **Set up wake word** aur **owner voice** ka guided setup follow karo. Wake-word model ko license ke kaaran installer mein bundle nahi kiya gaya hai; setup ke waqt publisher ki license terms review karo. Owner voice profile aapki apni awaaz se locally enroll hoti hai.
