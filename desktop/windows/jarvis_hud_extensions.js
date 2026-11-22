/* JARVIS HUD extension: lightweight animated Three.js reactor hologram. */
(() => {
  'use strict';
  if (window.__jarvisHudExtensionsLoaded) return;
  window.__jarvisHudExtensionsLoaded = true;

  const extensionScriptUrl = document.currentScript?.src || window.location.href;
  const vendorBase = new URL('vendor/', extensionScriptUrl);
  const orb = document.querySelector('.orb-wrapper');
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true;
  if (!orb || reducedMotion) return;

  const canvas = document.createElement('canvas');
  canvas.id = 'jx-holo-canvas';
  Object.assign(canvas.style, {
    position: 'absolute', inset: '0', width: '100%', height: '100%',
    zIndex: '2', pointerEvents: 'none'
  });
  orb.appendChild(canvas);

  const drawFallback = () => {
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    let active = true;
    let angle = 0;
    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const width = Math.max(1, canvas.clientWidth);
      const height = Math.max(1, canvas.clientHeight);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(orb);
    resize();
    const draw = () => {
      if (!active) return;
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      const cx = width / 2;
      const cy = height / 2;
      const radius = Math.min(width, height) * .34;
      ctx.clearRect(0, 0, width, height);
      angle += .012;
      for (let ring = 0; ring < 3; ring++) {
        ctx.beginPath();
        ctx.ellipse(cx, cy, radius * (1 - ring * .19),
          radius * (.34 + ring * .12), angle * (ring % 2 ? -.7 : 1),
          0, Math.PI * 2);
        ctx.strokeStyle = ring === 1 ? 'rgba(255,138,50,.8)' : 'rgba(0,220,255,.78)';
        ctx.lineWidth = 1.5;
        ctx.shadowBlur = 12;
        ctx.shadowColor = ctx.strokeStyle;
        ctx.stroke();
      }
      ctx.beginPath();
      ctx.arc(cx, cy, radius * .16, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(0,220,255,.22)';
      ctx.fill();
      ctx.strokeStyle = '#8eeaff';
      ctx.stroke();
      ctx.shadowBlur = 0;
      requestAnimationFrame(draw);
    };
    draw();
    window.addEventListener('pagehide', () => {
      active = false;
      observer.disconnect();
    }, { once: true });
  };

  import(new URL('three.module.js', vendorBase).href)
    .catch(error => {
      console.warn('JARVIS bundled Three.js unavailable; trying CDN fallback', error);
      return import('https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js');
    })
    .then(({ WebGLRenderer, Scene, PerspectiveCamera, TorusKnotGeometry,
      Mesh, MeshBasicMaterial, Group, AmbientLight, Clock }) => {
      if (!canvas.isConnected) return;
      const renderer = new WebGLRenderer({ canvas, alpha: true, antialias: true });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      const scene = new Scene();
      const camera = new PerspectiveCamera(42, 1, .1, 100);
      camera.position.z = 5;
      const rig = new Group();
      scene.add(rig);
      const geometry = new TorusKnotGeometry(1.15, .012, 180, 8, 2, 5);
      const material = new MeshBasicMaterial({
        color: 0x00dfff, transparent: true, opacity: .72
      });
      rig.add(new Mesh(geometry, material));
      const innerGeometry = new TorusKnotGeometry(.82, .009, 150, 6, 3, 4);
      const innerMaterial = new MeshBasicMaterial({
        color: 0xff8a32, transparent: true, opacity: .55
      });
      const inner = new Mesh(innerGeometry, innerMaterial);
      rig.add(inner);
      scene.add(new AmbientLight(0xffffff, .8));
      const clock = new Clock();
      const resize = () => {
        const width = Math.max(1, canvas.clientWidth);
        const height = Math.max(1, canvas.clientHeight);
        renderer.setSize(width, height, false);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
      };
      const observer = new ResizeObserver(resize);
      observer.observe(orb);
      resize();
      let active = true;
      const draw = () => {
        if (!active) return;
        const time = clock.getElapsedTime();
        rig.rotation.y = time * .22;
        rig.rotation.x = Math.sin(time * .3) * .18;
        inner.rotation.z = -time * .42;
        renderer.render(scene, camera);
        requestAnimationFrame(draw);
      };
      draw();
      window.addEventListener('pagehide', () => {
        active = false;
        observer.disconnect();
        geometry.dispose();
        material.dispose();
        innerGeometry.dispose();
        innerMaterial.dispose();
        renderer.dispose();
      }, { once: true });
    })
    .catch(error => {
      console.warn('JARVIS Three.js hologram unavailable; starting native canvas fallback', error);
      drawFallback();
    });
})();
