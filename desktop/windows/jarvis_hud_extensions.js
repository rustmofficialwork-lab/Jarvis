/* JARVIS HUD extensions: opt-in hand gestures and a lightweight Three.js hologram. */
(() => {
  'use strict';
  if (window.__jarvisHudExtensionsLoaded) return;
  window.__jarvisHudExtensionsLoaded = true;
  const style = document.createElement('style');
  style.textContent = '#jx-extensions{position:fixed;right:18px;bottom:18px;z-index:260;display:flex;gap:8px;align-items:center;font:600 13px Rajdhani,sans-serif}#jx-extensions button{background:rgba(2,20,32,.94);border:1px solid #00e5ff;color:#a4f4ff;padding:9px 13px;cursor:pointer}#jx-extensions button[aria-pressed=true]{background:rgba(0,229,255,.24);box-shadow:0 0 12px #00bfe5}#jx-ext-status{max-width:220px;color:#a4f4ff;background:rgba(2,20,32,.88);padding:7px 10px;border-left:2px solid #00e5ff}#jx-camera-preview{position:fixed;right:18px;bottom:64px;width:180px;aspect-ratio:4/3;object-fit:cover;z-index:259;border:1px solid #00e5ff;transform:scaleX(-1);display:none;background:#020b14}#jx-holo-canvas{position:absolute;inset:0;width:100%;height:100%;z-index:2;pointer-events:none}.hud-inner.jx-gesture-active .orb-wrapper{filter:drop-shadow(0 0 20px rgba(0,229,255,.9))}@media(max-width:700px){#jx-extensions{right:8px;bottom:8px;flex-wrap:wrap;justify-content:flex-end}#jx-ext-status{max-width:145px}#jx-camera-preview{right:8px;bottom:92px;width:132px}}@media(prefers-reduced-motion:reduce){#jx-holo-canvas{display:none}}';
  document.head.appendChild(style);
  const controls=document.createElement('div');controls.id='jx-extensions';
  controls.innerHTML='<span id="jx-ext-status" role="status">3D hologram ready · Camera off</span><button id="jx-gesture-toggle" type="button" aria-pressed="false">ENABLE GESTURES</button>';
  document.body.appendChild(controls);
  const preview=document.createElement('video');preview.id='jx-camera-preview';preview.autoplay=true;preview.muted=true;preview.playsInline=true;preview.setAttribute('aria-label','Local hand gesture camera preview');document.body.appendChild(preview);
  const status=document.getElementById('jx-ext-status'),toggle=document.getElementById('jx-gesture-toggle'),hud=document.querySelector('.hud-inner'),orb=document.querySelector('.orb-wrapper');
  if(orb){
    const canvas=document.createElement('canvas');canvas.id='jx-holo-canvas';orb.appendChild(canvas);
    import('https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js').then(({WebGLRenderer,Scene,PerspectiveCamera,TorusKnotGeometry,Mesh,MeshBasicMaterial,Group,AmbientLight,Clock})=>{
      if(!canvas.isConnected)return;
      const renderer=new WebGLRenderer({canvas,alpha:true,antialias:true});renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
      const scene=new Scene(),camera=new PerspectiveCamera(42,1,.1,100);camera.position.z=5;
      const rig=new Group();hologramRig=rig;scene.add(rig);
      const geometry=new TorusKnotGeometry(1.15,.012,180,8,2,5),material=new MeshBasicMaterial({color:0x00dfff,transparent:true,opacity:.72});
      rig.add(new Mesh(geometry,material));
      const innerGeometry=new TorusKnotGeometry(.82,.009,150,6,3,4),innerMaterial=new MeshBasicMaterial({color:0xff8a32,transparent:true,opacity:.55}),inner=new Mesh(innerGeometry,innerMaterial);rig.add(inner);scene.add(new AmbientLight(0xffffff,.8));
      const clock=new Clock(),resize=()=>{const w=Math.max(1,canvas.clientWidth),h=Math.max(1,canvas.clientHeight);renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();};
      const observer=new ResizeObserver(resize);observer.observe(orb);resize();let active=true;
      const draw=()=>{if(!active)return;const t=clock.getElapsedTime();rig.rotation.y=t*.22;rig.rotation.x=Math.sin(t*.3)*.18;inner.rotation.z=-t*.42;renderer.render(scene,camera);requestAnimationFrame(draw);};draw();
      window.addEventListener('pagehide',()=>{active=false;observer.disconnect();geometry.dispose();material.dispose();innerGeometry.dispose();innerMaterial.dispose();renderer.dispose();},{once:true});
      status.textContent='3D hologram ready · Camera off';
    }).catch(err=>{console.warn('JARVIS Three.js hologram unavailable',err);status.textContent='3D module unavailable · HUD remains active';});
  }
  let stream=null,landmarker=null,raf=0,lastSwipe=0,lastPinch=false,lastFist=false,lastX=null,hologramRig=null;
  const setStatus=s=>{status.textContent=s;};
  const clickHudTarget=()=>{const candidates=[...document.querySelectorAll('[data-hud]')].filter(el=>el.getClientRects().length);if(!candidates.length)return;const x=window.innerWidth/2,y=window.innerHeight/2;candidates.sort((a,b)=>{const score=el=>{const r=el.getBoundingClientRect();return Math.hypot(r.left+r.width/2-x,r.top+r.height/2-y);};return score(a)-score(b);});candidates[0].dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));};
  const stop=()=>{cancelAnimationFrame(raf);raf=0;if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}preview.srcObject=null;preview.style.display='none';landmarker?.close?.();landmarker=null;toggle.setAttribute('aria-pressed','false');toggle.textContent='ENABLE GESTURES';hud?.classList.remove('jx-gesture-active');setStatus('3D hologram ready · Camera off');};
  const dist=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
  const detect=results=>{const hand=results.landmarks?.[0];if(!hand)return;const pinch=dist(hand[4],hand[8])<.055,fist=[8,12,16,20].every(i=>hand[i].y>hand[i-2].y),now=performance.now(),wrist=hand[0];if(pinch&&!lastPinch){clickHudTarget();setStatus('Gesture: pinch click');}if(fist&&!lastFist){hud?.classList.toggle('jx-gesture-active');setStatus('Gesture: fist · hologram pulse');}if(lastX!==null&&Math.abs(wrist.x-lastX)>.20&&now-lastSwipe>900){lastSwipe=now;if(hologramRig)hologramRig.rotation.y+=(wrist.x>lastX?-.65:.65);setStatus('Gesture: swipe · hologram rotated');}lastPinch=pinch;lastFist=fist;lastX=wrist.x;};
  const frame=()=>{if(!landmarker||preview.readyState<2){raf=requestAnimationFrame(frame);return;}try{detect(landmarker.detectForVideo(preview,performance.now()));}catch(err){console.warn('Gesture frame skipped',err);}raf=requestAnimationFrame(frame);};
  const start=async()=>{if(!navigator.mediaDevices?.getUserMedia){setStatus('Camera unavailable in this WebView');return;}toggle.disabled=true;try{setStatus('Requesting camera permission…');stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:{ideal:640},height:{ideal:480}},audio:false});preview.srcObject=stream;preview.style.display='block';await preview.play();setStatus('Loading local hand tracking…');const vision=await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14');const fileset=await vision.FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm');landmarker=await vision.HandLandmarker.createFromOptions(fileset,{baseOptions:{modelAssetPath:'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',delegate:'GPU'},runningMode:'VIDEO',numHands:1});lastX=null;lastPinch=false;lastFist=false;toggle.setAttribute('aria-pressed','true');toggle.textContent='DISABLE GESTURES';setStatus('Gestures active · pinch click · fist pulse · swipe');raf=requestAnimationFrame(frame);}catch(err){console.warn('JARVIS gesture setup failed',err);stop();setStatus(err?.name==='NotAllowedError'?'Camera permission denied':'Gesture setup failed · check internet/WebView');}finally{toggle.disabled=false;}};
  toggle.addEventListener('click',()=>{if(stream)stop();else void start();});window.addEventListener('beforeunload',stop,{once:true});
})();