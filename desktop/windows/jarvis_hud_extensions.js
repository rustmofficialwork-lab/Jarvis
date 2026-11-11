/* JARVIS HUD extensions: opt-in hand gestures and a lightweight Three.js hologram. */
(() => {
  'use strict';
  if (window.__jarvisHudExtensionsLoaded) return;
  window.__jarvisHudExtensionsLoaded = true;
  const extensionScriptUrl = document.currentScript?.src || window.location.href;
  const vendorBase = new URL('vendor/', extensionScriptUrl);
  const loadVisionRuntime = async () => {
    try {
      return await import(new URL('mediapipe/vision_bundle.mjs', vendorBase).href);
    } catch (localError) {
      console.warn('JARVIS bundled MediaPipe runtime unavailable; trying CDN fallback', localError);
      return await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14');
    }
  };
  const loadVisionFileset = async vision => {
    try {
      return await vision.FilesetResolver.forVisionTasks(new URL('mediapipe/wasm/', vendorBase).href);
    } catch (localError) {
      console.warn('JARVIS bundled MediaPipe WASM unavailable; trying CDN fallback', localError);
      return await vision.FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm');
    }
  };
  const style = document.createElement('style');
  style.textContent = '#jx-extensions{position:fixed;right:18px;bottom:18px;z-index:260;display:flex;gap:8px;align-items:center;font:600 13px Rajdhani,sans-serif}#jx-extensions button{background:rgba(2,20,32,.94);border:1px solid #00e5ff;color:#a4f4ff;padding:9px 13px;cursor:pointer}#jx-extensions button[aria-pressed=true]{background:rgba(0,229,255,.24);box-shadow:0 0 12px #00bfe5}#jx-ext-status{max-width:220px;color:#a4f4ff;background:rgba(2,20,32,.88);padding:7px 10px;border-left:2px solid #00e5ff}#jx-camera-preview{position:fixed;right:18px;bottom:64px;width:180px;aspect-ratio:4/3;object-fit:cover;z-index:259;border:1px solid #00e5ff;transform:scaleX(-1);display:none;background:#020b14}#jx-holo-canvas{position:absolute;inset:0;width:100%;height:100%;z-index:2;pointer-events:none}.hud-inner.jx-gesture-active .orb-wrapper{filter:drop-shadow(0 0 20px rgba(0,229,255,.9))}@media(max-width:700px){#jx-extensions{right:8px;bottom:8px;flex-wrap:wrap;justify-content:flex-end}#jx-ext-status{max-width:145px}#jx-camera-preview{right:8px;bottom:92px;width:132px}}@media(prefers-reduced-motion:reduce){#jx-holo-canvas{display:none}}';
  document.head.appendChild(style);
  const controls=document.createElement('div');controls.id='jx-extensions';
  controls.innerHTML='<span id="jx-ext-status" role="status">3D hologram ready · Camera off</span><button id="jx-gesture-toggle" type="button" aria-pressed="false">ENABLE GESTURES</button><button id="jx-face-toggle" type="button" aria-pressed="false">FACE PRESENCE</button>';
  document.body.appendChild(controls);
  const preview=document.createElement('video');preview.id='jx-camera-preview';preview.autoplay=true;preview.muted=true;preview.playsInline=true;preview.setAttribute('aria-label','Local hand gesture camera preview');document.body.appendChild(preview);
  const status=document.getElementById('jx-ext-status'),toggle=document.getElementById('jx-gesture-toggle'),faceToggle=document.getElementById('jx-face-toggle'),hud=document.querySelector('.hud-inner'),orb=document.querySelector('.orb-wrapper');
  if(orb){
    const canvas=document.createElement('canvas');canvas.id='jx-holo-canvas';orb.appendChild(canvas);
    import(new URL('three.module.js', vendorBase).href).catch(localError=>{console.warn('JARVIS bundled Three.js unavailable; trying CDN fallback',localError);return import('https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js');}).then(({WebGLRenderer,Scene,PerspectiveCamera,TorusKnotGeometry,Mesh,MeshBasicMaterial,Group,AmbientLight,Clock})=>{
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
    }).catch(err=>{console.warn('JARVIS Three.js hologram unavailable; starting native canvas fallback',err);const ctx=canvas.getContext('2d');if(!ctx){status.textContent='Hologram unavailable · HUD remains active';return;}let active=true,angle=0;const resize=()=>{const dpr=Math.min(window.devicePixelRatio||1,2),w=Math.max(1,canvas.clientWidth),h=Math.max(1,canvas.clientHeight);canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);};const observer=new ResizeObserver(resize);observer.observe(orb);resize();const draw=()=>{if(!active)return;const w=canvas.clientWidth,h=canvas.clientHeight,cx=w/2,cy=h/2,r=Math.min(w,h)*.34;ctx.clearRect(0,0,w,h);angle+=.012;for(let ring=0;ring<3;ring++){ctx.beginPath();ctx.ellipse(cx,cy,r*(1-ring*.19),r*(.34+ring*.12),angle*(ring%2?-.7:1),0,Math.PI*2);ctx.strokeStyle=ring===1?'rgba(255,138,50,.8)':'rgba(0,220,255,.78)';ctx.lineWidth=1.5;ctx.shadowBlur=12;ctx.shadowColor=ctx.strokeStyle;ctx.stroke();}ctx.beginPath();ctx.arc(cx,cy,r*.16,0,Math.PI*2);ctx.fillStyle='rgba(0,220,255,.22)';ctx.fill();ctx.strokeStyle='#8eeaff';ctx.stroke();ctx.shadowBlur=0;requestAnimationFrame(draw);};draw();window.addEventListener('pagehide',()=>{active=false;observer.disconnect();},{once:true});status.textContent='Hologram ready · native canvas fallback · Camera off';});
  }
  let stream=null,cameraUsers=0,cameraPromise=null,landmarker=null,raf=0,lastSwipe=0,lastPinch=false,lastFist=false,swipeStartX=null,swipeStartAt=0,lastGestureAt=0,hologramRig=null,faceDetector=null,faceRaf=0,facePreview=null;
  const acquireCamera=async video=>{
    if(!stream){
      if(!cameraPromise){
        cameraPromise=navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'user'},width:{ideal:640},height:{ideal:480}},audio:false})
          .catch(firstError=>{
            console.warn('JARVIS camera preferred constraints unavailable; retrying with defaults',firstError);
            return navigator.mediaDevices.getUserMedia({video:true,audio:false});
          })
          .then(value=>(stream=value,value))
          .finally(()=>{cameraPromise=null;});
      }
      await cameraPromise;
    }else if(cameraPromise){await cameraPromise;}
    cameraUsers++;video.srcObject=stream;
    try{await video.play();}catch(error){cameraUsers=Math.max(0,cameraUsers-1);video.srcObject=null;throw error;}
    return stream;
  };
  const releaseCamera=video=>{video.srcObject=null;cameraUsers=Math.max(0,cameraUsers-1);if(cameraUsers===0&&stream){stream.getTracks().forEach(track=>track.stop());stream=null;}};
  const createVisionTask=async(factory,options)=>{try{return await factory({...options,baseOptions:{...options.baseOptions,delegate:'GPU'}});}catch(gpuError){console.warn('JARVIS GPU delegate unavailable; retrying on CPU',gpuError);return await factory({...options,baseOptions:{...options.baseOptions,delegate:'CPU'}});}};
  const setStatus=s=>{status.textContent=s;};
  const gesture=window.JARVISGestureLogic;
  if(!gesture){
    toggle.disabled=true;
    setStatus('Gesture logic unavailable · restart JARVIS');
  }
  const waitForVideo=video=>new Promise((resolve,reject)=>{
    if(video.readyState>=2){resolve();return;}
    let done=false;
    const finish=(error)=>{if(done)return;done=true;clearTimeout(timer);video.removeEventListener('loadeddata',onReady);video.removeEventListener('error',onError);error?reject(error):resolve();};
    const onReady=()=>finish();
    const onError=()=>finish(new Error('Camera stream did not produce video frames'));
    const timer=setTimeout(()=>finish(new Error('Camera video timed out; check privacy permissions and camera use')),10000);
    video.addEventListener('loadeddata',onReady,{once:true});
    video.addEventListener('error',onError,{once:true});
  });
  const clickHudTarget=hand=>{
    const point=gesture.toViewport(hand[8].x,hand[8].y,window.innerWidth,window.innerHeight,true);
    const hit=document.elementFromPoint(point.x,point.y);
    const target=hit?.closest?.('[data-hud]');
    if(!target||!target.getClientRects().length||target.disabled||target.getAttribute('aria-disabled')==='true')return false;
    target.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window,clientX:point.x,clientY:point.y}));
    return true;
  };
  const stop=()=>{cancelAnimationFrame(raf);raf=0;if(preview.srcObject){releaseCamera(preview);}preview.style.display='none';landmarker?.close?.();landmarker=null;lastPinch=false;lastFist=false;swipeStartX=null;swipeStartAt=0;toggle.setAttribute('aria-pressed','false');toggle.textContent='ENABLE GESTURES';hud?.classList.remove('jx-gesture-active');setStatus(facePreview.srcObject?'Face presence active · camera in use':'3D hologram ready · Camera off');};
  facePreview=document.createElement('video');facePreview.muted=true;facePreview.autoplay=true;facePreview.playsInline=true;facePreview.style.cssText='position:fixed;right:18px;bottom:64px;width:180px;display:none;opacity:.01;pointer-events:none';document.body.appendChild(facePreview);
  let facePresent=false;
  const stopFace=()=>{cancelAnimationFrame(faceRaf);faceRaf=0;if(facePreview.srcObject){releaseCamera(facePreview);}facePreview.style.display='none';faceDetector?.close?.();faceDetector=null;facePresent=false;hud?.classList.remove('jx-face-present');faceToggle.setAttribute('aria-pressed','false');faceToggle.textContent='FACE PRESENCE';setStatus(stream?'Gestures active':'3D hologram ready · Camera off');};
  const faceFrame=()=>{if(!faceDetector||facePreview.readyState<2){faceRaf=requestAnimationFrame(faceFrame);return;}try{const result=faceDetector.detectForVideo(facePreview,performance.now());const found=!!(result.detections&&result.detections.length);if(found!==facePresent){facePresent=found;hud?.classList.toggle('jx-face-present',found);setStatus(found?'Face present · local presence detected':'Waiting for face · no identity verification');}}catch(err){console.warn('Face presence frame skipped',err);}faceRaf=requestAnimationFrame(faceFrame);};
  const startFace=async()=>{if(!navigator.mediaDevices?.getUserMedia){setStatus('Camera unavailable in this WebView');return;}faceToggle.disabled=true;try{setStatus('Requesting camera permission for face presence…');await acquireCamera(facePreview);facePreview.style.display='block';const vision=await loadVisionRuntime();const fileset=await loadVisionFileset(vision);faceDetector=await createVisionTask(opts=>vision.FaceDetector.createFromOptions(fileset,opts),{baseOptions:{modelAssetPath:'https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite'},runningMode:'VIDEO',minDetectionConfidence:.65});faceToggle.setAttribute('aria-pressed','true');faceToggle.textContent='STOP FACE CHECK';setStatus('Face presence active · identity is not verified');faceRaf=requestAnimationFrame(faceFrame);}catch(err){console.warn('JARVIS face presence setup failed',err);stopFace();setStatus(err?.name==='NotAllowedError'?'Camera permission denied':'Face detector unavailable · check internet, camera and WebView');}finally{faceToggle.disabled=false;}};
  faceToggle.addEventListener('click',()=>{if(facePreview.srcObject)stopFace();else void startFace();});
  let lastInferenceAt=0,lastVideoTime=-1,swipeState=gesture?.emptySwipeState?.()||{startX:null,startAt:0,lastAt:-Infinity};
  const detect=results=>{
    const hand=results.landmarks?.[0],now=performance.now();
    if(!hand){lastPinch=false;lastFist=false;swipeState=gesture.emptySwipeState();return;}
    const pinch=gesture.isPinching(hand),fist=gesture.isFist(hand);
    if(pinch&&!lastPinch&&now-lastGestureAt>650){
      if(clickHudTarget(hand)){lastGestureAt=now;setStatus('Gesture: pinch · HUD action triggered');}
      else setStatus('Pinch detected · point at a highlighted HUD control');
    }
    if(fist&&!lastFist&&now-lastGestureAt>650){
      hud?.classList.toggle('jx-gesture-active');lastGestureAt=now;setStatus('Gesture: fist · hologram pulse');
    }
    const swipe=gesture.updateSwipe(hand[0].x,now,swipeState);
    swipeState=swipe.state;
    if(swipe.direction){
      lastSwipe=now;
      if(hologramRig){hologramRig.rotation.y+=(swipe.direction>0?-.65:.65);setStatus('Gesture: swipe · hologram rotated');}
    }
    lastPinch=pinch;lastFist=fist;
  };
  const frame=()=>{
    if(!landmarker||preview.readyState<2){raf=requestAnimationFrame(frame);return;}
    const now=performance.now();
    if(preview.currentTime!==lastVideoTime&&now-lastInferenceAt>=80){
      lastVideoTime=preview.currentTime;lastInferenceAt=now;
      try{detect(landmarker.detectForVideo(preview,now));}
      catch(err){console.warn('Gesture frame skipped',err);setStatus('Tracking paused · move into camera view');}
    }
    raf=requestAnimationFrame(frame);
  };
  const start=async()=>{
    if(!gesture){setStatus('Gesture logic unavailable · restart JARVIS');return;}
    if(!navigator.mediaDevices?.getUserMedia){setStatus('Camera unavailable · run JARVIS in the Windows desktop app');return;}
    toggle.disabled=true;
    try{
      setStatus('Requesting camera permission…');
      await acquireCamera(preview);
      preview.style.display='block';
      await waitForVideo(preview);
      setStatus('Loading local hand-tracking model…');
      const vision=await loadVisionRuntime();
      const fileset=await loadVisionFileset(vision);
      const modelUrl=new URL('mediapipe/models/hand_landmarker.task',vendorBase).href;
      landmarker=await createVisionTask(opts=>vision.HandLandmarker.createFromOptions(fileset,opts),{
        baseOptions:{modelAssetPath:modelUrl},runningMode:'VIDEO',numHands:1,
        minHandDetectionConfidence:.55,minHandPresenceConfidence:.5,minTrackingConfidence:.5
      });
      swipeState=gesture.emptySwipeState();lastPinch=false;lastFist=false;lastVideoTime=-1;lastInferenceAt=0;
      toggle.setAttribute('aria-pressed','true');toggle.textContent='DISABLE GESTURES';
      setStatus('Gestures active · pinch HUD · fist pulse · swipe rotate');
      raf=requestAnimationFrame(frame);
    }catch(err){
      console.warn('JARVIS gesture setup failed',err);stop();
      const message=err?.name==='NotAllowedError'?'Camera permission denied':
        err?.name==='NotFoundError'?'No camera detected':
        /timed out/i.test(err?.message||'')?'Camera did not start · close other camera apps':
        'Gesture setup failed · verify bundled vision assets and camera permissions';
      setStatus(message);
    }finally{toggle.disabled=false;}
  };
  toggle.addEventListener('click',()=>{if(preview.srcObject)stop();else void start();});window.addEventListener('beforeunload',()=>{stop();stopFace();},{once:true});
})();