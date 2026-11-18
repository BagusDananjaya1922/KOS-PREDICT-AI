/* GusSearch Kost — efek interaksi ringan. Berdiri sendiri, tidak menyentuh script bawaan dashboard. */
(() => {
    // Sorot cahaya mengikuti kursor di kartu ber-class .card-hover
    document.addEventListener('pointermove', (e) => {
        const card = e.target.closest && e.target.closest('.card-hover');
        if (!card) return;
        const r = card.getBoundingClientRect();
        card.style.setProperty('--mx', (e.clientX - r.left) + 'px');
        card.style.setProperty('--my', (e.clientY - r.top) + 'px');
    }, { passive: true });

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    // Cahaya warna di hero bergeser tipis mengikuti kursor
    const hero = document.querySelector('#tab-beranda > div:first-child');
    if (!hero) return;
    const glows = hero.querySelectorAll('.blur-3xl');
    hero.addEventListener('pointermove', (e) => {
        const r = hero.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width - 0.5;
        const y = (e.clientY - r.top) / r.height - 0.5;
        glows.forEach((g, i) => {
            const k = i % 2 ? -1 : 1;
            g.style.transition = 'transform .6s ease-out';
            g.style.transform = `translate(${x * 36 * k}px, ${y * 24 * k}px)`;
        });
    }, { passive: true });
})();