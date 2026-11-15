# JARVIS: download karo aur use karo

Windows app (`JARVIS-Setup-x64.exe`) GitHub khud banata hai. Aapko code compile nahi karna.

## Pehli baar (sirf ek baar, ~5 minute)
1. Is zip ke andar ka sab kuch apne GitHub repo (`rustmofficialwork-lab/Jarvis`) ki `main` branch me upload/push karo (purani files replace ho jayengi).
2. Repo me **Actions** tab kholo. "JARVIS Project Checks and Windows Build" apne aap chalega (10-20 minute).
3. Green tick aane ke baad:
   - **Releases -> "JARVIS Latest Windows Build"** se `JARVIS-Setup-x64.exe` download karo, **ya**
   - us Actions run ke neeche **Artifacts -> JARVIS-Windows-Installer-x64** se download karo.

## Install
1. `JARVIS-Setup-x64.exe` chalao. "Install offline AI" ka box tick rehne do (internet se ~2 GB, sirf ek baar) - isse bina internet ke bhi AI chalega.
2. Windows "SmartScreen" warning de to **More info -> Run anyway** dabao (app abhi code-signed nahi hai).
3. JARVIS kholo. Typing se chat turant chalti hai. Try karo: `good morning jarvis`, `notepad kholo aur phir calculator kholo`, `brain check`.

## Voice ke liye (ek baar)
Voice ke liye app ke andar **Set up wake word** aur **owner voice** ka guided setup hota hai (wake-word model ka license bundle karne ki ijazat nahi deta, aur owner voice aapki apni awaaz se banti hai).
