# JARVIS: download karo aur use karo

Windows installer GitHub Actions automatically banata hai. App install karne ke liye source ZIP ko repository mein upload karne ya code compile karne ki zaroorat nahi hai.

## Installer download karo

1. Repository ka **Actions** tab kholo: https://github.com/rustmofficialwork-lab/Jarvis/actions
2. Sabse naya **JARVIS Project Checks and Windows Build** run kholo.
3. Run ke **completed** hone aur green **Success** result aane ka wait karo. Installer build fail ya in-progress ho to download ko ready mat samjho.
4. **Artifacts** section se `JARVIS-Full-Offline-Setup` download karo. ZIP mein `JARVIS-Setup-x64.exe`, required `.bin` data slices aur SHA-256 file hoti hai. Setup.exe aur sabhi `.bin` files ko ek hi folder mein rakho.
5. Agar aapne `main` branch mein code change push kiya hai, to us push ke baad bana hua latest run hi check karo. Zaroorat par Actions workflow ke **Run workflow** option se build manually start kiya ja sakta hai.

## Install

1. Downloaded `JARVIS-Full-Offline-Setup.zip` extract karo. `JARVIS-Setup-x64.exe` aur uske saare `.bin` slices ek hi folder mein rehne do; phir Setup.exe chalao.
2. Installer ke andar Qwen3.5 4B model files aur Ollama runtime pehle se bundled hain. Installation ke waqt setup local bundle ko verify karke model ki local inference test karta hai; model ke liye alag se 3.3–4.0 GB download nahi karna padta. General AI chat isi ek local model se online aur offline dono mein chalega; AI API key ya cloud AI backend ki zaroorat nahi. Live web search aur internet-only features ke liye internet chahiye.
3. App abhi code-signed nahi hai, isliye Windows SmartScreen warning dikha sakta hai. Publisher verify kiye bina kisi unexpected installer ko run mat karo.
4. JARVIS kholo. Typing se chat use kar sakte ho. Try: `good morning jarvis`, `notepad kholo aur phir calculator kholo`, `brain check`.

## Voice setup

Voice ke liye app ke andar **Set up wake word** aur **owner voice** ka guided setup follow karo. Wake-word model ko license ke kaaran installer mein bundle nahi kiya gaya hai; setup ke waqt publisher ki license terms review karo. Owner voice profile aapki apni awaaz se locally enroll hoti hai.
