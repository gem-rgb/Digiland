/**
 * useHeroAnimations — Anime.js-powered hero section animation controller.
 *
 * Provides React hooks that orchestrate all hero section animations using
 * Anime.js timelines, staggered reveals, and looping scene transitions.
 * Replaces the previous CSS-only animation approach with a more expressive,
 * choreographed motion system.
 */
import { useEffect, useRef, useState } from 'react';
import anime from 'animejs';

function prefersReducedMotion() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false;
  }

  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function revealHeroElements(hero: HTMLElement) {
  const selectors = [
    '.hero-entrance-item',
    '.hero-trust-item',
    '.hero-right-card',
    '.hero-stat-card',
    '.hero-ambient-fx',
    '.hero-market-chip',
    '.hero-floating-indicator',
  ];

  selectors.forEach((selector) => {
    hero.querySelectorAll<HTMLElement>(selector).forEach((element) => {
      element.style.opacity = '1';
      element.style.transform = 'none';
      element.style.clipPath = 'none';
      element.style.animation = 'none';
      element.style.filter = 'none';
    });
  });
}

/* ------------------------------------------------------------------ */
/*  Master Hero Timeline                                               */
/* ------------------------------------------------------------------ */

/**
 * useHeroEntrance — Plays the staggered hero entrance animation on mount.
 *
 * Animates all left-side elements (badge, headline, sub-headlines, CTAs,
 * trust indicators, stats) and right-side cards with precisely timed
 * Anime.js staggered reveals.
 */
export function useHeroEntrance() {
  const heroRef = useRef<HTMLDivElement>(null);
  const hasPlayed = useRef(false);

  useEffect(() => {
    const hero = heroRef.current;
    if (!hero || hasPlayed.current) return;

    if (prefersReducedMotion()) {
      hasPlayed.current = true;
      revealHeroElements(hero);
      return;
    }

    const play = () => {
      if (hasPlayed.current) return;
      hasPlayed.current = true;

      const leftItems = hero.querySelectorAll('.hero-entrance-item');
      anime({
        targets: leftItems,
        opacity: [0, 1],
        translateY: [24, 0],
        duration: 700,
        delay: anime.stagger(120, { start: 180 }),
        easing: 'easeOutCubic',
      });

      const badge = hero.querySelector('.hero-badge');
      if (badge) {
        anime({
          targets: badge,
          opacity: [0, 1],
          scale: [0.9, 1],
          duration: 520,
          delay: 90,
          easing: 'easeOutCubic',
        });
      }

      const headline = hero.querySelector('.hero-headline');
      if (headline) {
        anime({
          targets: headline,
          opacity: [0, 1],
          clipPath: ['inset(0 100% 0 0)', 'inset(0 0% 0 0)'],
          duration: 820,
          delay: 320,
          easing: 'easeInOutQuart',
        });
      }

      const trustItems = hero.querySelectorAll('.hero-trust-item');
      anime({
        targets: trustItems,
        opacity: [0, 1],
        translateX: [-12, 0],
        duration: 480,
        delay: anime.stagger(70, { start: 980 }),
        easing: 'easeOutCubic',
      });

      const rightCards = hero.querySelectorAll('.hero-right-card');
      anime({
        targets: rightCards,
        opacity: [0, 1],
        translateX: [36, 0],
        scale: [0.97, 1],
        duration: 600,
        delay: anime.stagger(130, { start: 460 }),
        easing: 'easeOutCubic',
      });

      const statCards = hero.querySelectorAll('.hero-stat-card');
      anime({
        targets: statCards,
        opacity: [0, 1],
        translateY: [14, 0],
        scale: [0.96, 1],
        duration: 480,
        delay: anime.stagger(90, { start: 1200 }),
        easing: 'easeOutCubic',
      });

      const ambientFx = hero.querySelectorAll('.hero-ambient-fx');
      anime({
        targets: ambientFx,
        opacity: [0, 1],
        duration: 900,
        delay: anime.stagger(120, { start: 80 }),
        easing: 'easeOutCubic',
      });

      const marketChips = hero.querySelectorAll('.hero-market-chip');
      anime({
        targets: marketChips,
        opacity: [0, 1],
        translateY: [12, 0],
        scale: [0.985, 1],
        duration: 620,
        delay: anime.stagger(120, { start: 900 }),
        easing: 'easeOutCubic',
      });

      const floatingIndicators = hero.querySelectorAll('.hero-floating-indicator');
      anime({
        targets: floatingIndicators,
        opacity: [0, 1],
        duration: 560,
        delay: anime.stagger(100, { start: 1180 }),
        easing: 'easeOutCubic',
      });
    };

    if (typeof IntersectionObserver === 'undefined') {
      play();
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          play();
          observer.disconnect();
        }
      },
      {
        threshold: 0.18,
        rootMargin: '48px 0px -8% 0px',
      }
    );

    observer.observe(hero);
    return () => observer.disconnect();
  }, []);

  return heroRef;
}

/* ------------------------------------------------------------------ */
/*  Transaction Journey Scene Cycler                                   */
/* ------------------------------------------------------------------ */

/**
 * useJourneyCycler — Animates the transaction journey scene transitions
 * using Anime.js for smooth crossfade + slide effects.
 *
 * Returns the active scene index and a ref for the scene container.
 */
export function useJourneyCycler(sceneCount: number, interval = 3500) {
  const [activeScene, setActiveScene] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const animating = useRef(false);

  useEffect(() => {
    const timer = setInterval(() => {
      setActiveScene((prev) => (prev + 1) % sceneCount);
    }, interval);
    return () => clearInterval(timer);
  }, [sceneCount, interval]);

  // Animate the scene transition
  useEffect(() => {
    if (!containerRef.current || animating.current) return;
    animating.current = true;

    const container = containerRef.current;
    const scenes = container.querySelectorAll('.journey-scene');
    const indicators = container.querySelectorAll('.journey-indicator');

    // Fade out all scenes
    anime({
      targets: scenes,
      opacity: 0,
      translateY: -8,
      duration: 300,
      easing: 'easeInCubic',
      complete: () => {
        // Fade in active scene
        const activeEl = scenes[activeScene] as HTMLElement;
        if (activeEl) {
          activeEl.style.maxHeight = '120px';
          anime({
            targets: activeEl,
            opacity: [0, 1],
            translateY: [12, 0],
            maxHeight: [0, 120],
            duration: 400,
            easing: 'easeOutCubic',
          });
        }
        // Hide others
        scenes.forEach((scene, i) => {
          if (i !== activeScene) {
            const el = scene as HTMLElement;
            el.style.maxHeight = '0px';
          }
        });
      },
    });

    // Animate indicators
    anime({
      targets: indicators,
      width: (el: Element, i: number) => i === activeScene ? 24 : 6,
      backgroundColor: (el: Element, i: number) =>
        i === activeScene ? '#059669' : '#a7f3d0',
      duration: 350,
      easing: 'easeOutCubic',
    });

    setTimeout(() => { animating.current = false; }, 700);
  }, [activeScene]);

  return { activeScene, containerRef };
}

/* ------------------------------------------------------------------ */
/*  Verification Timeline Animation                                    */
/* ------------------------------------------------------------------ */

/**
 * useTimelineAnimation — Animates verification timeline nodes appearing
 * one by one with stamp-in effect and connector line growth.
 */
export function useTimelineAnimation() {
  const timelineRef = useRef<HTMLDivElement>(null);
  const hasAnimated = useRef(false);

  useEffect(() => {
    if (!timelineRef.current || hasAnimated.current) return;
    hasAnimated.current = true;

    const container = timelineRef.current;

    // Use IntersectionObserver to trigger on scroll into view
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            animateTimeline(container);
            observer.disconnect();
          }
        });
      },
      { threshold: 0.3 }
    );
    observer.observe(container);

    return () => observer.disconnect();
  }, []);
}

function animateTimeline(container: HTMLDivElement) {
  const nodes = container.querySelectorAll('.timeline-node');
  const connectors = container.querySelectorAll('.timeline-connector');
  const labels = container.querySelectorAll('.timeline-label');

  // Stamp in nodes
  anime({
    targets: nodes,
    opacity: [0, 1],
    scale: [0, 1],
    duration: 400,
    delay: anime.stagger(200, { start: 300 }),
    easing: 'easeOutBack',
  });

  // Grow connectors
  anime({
    targets: connectors,
    scaleY: [0, 1],
    duration: 300,
    delay: anime.stagger(200, { start: 500 }),
    easing: 'easeOutCubic',
  });

  // Slide in labels
  anime({
    targets: labels,
    opacity: [0, 1],
    translateX: [-12, 0],
    duration: 400,
    delay: anime.stagger(200, { start: 400 }),
    easing: 'easeOutCubic',
  });
}

/* ------------------------------------------------------------------ */
/*  Progress Bar Animation                                             */
/* ------------------------------------------------------------------ */

/**
 * useProgressBars — Animates progress bars filling up when scrolled into view.
 */
export function useProgressBars() {
  const progressRef = useRef<HTMLDivElement>(null);
  const hasAnimated = useRef(false);

  useEffect(() => {
    if (!progressRef.current || hasAnimated.current) return;

    const container = progressRef.current;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !hasAnimated.current) {
            hasAnimated.current = true;
            animateProgressBars(container);
            observer.disconnect();
          }
        });
      },
      { threshold: 0.3 }
    );
    observer.observe(container);

    return () => observer.disconnect();
  }, []);
}

function animateProgressBars(container: HTMLDivElement) {
  const bars = container.querySelectorAll('.progress-fill');

  anime({
    targets: bars,
    width: (el: Element) => el.getAttribute('data-progress') + '%',
    duration: 1200,
    delay: anime.stagger(150, { start: 200 }),
    easing: 'easeOutQuart',
  });
}

/* ------------------------------------------------------------------ */
/*  Escrow Flow Animation                                              */
/* ------------------------------------------------------------------ */

/**
 * useEscrowFlow — Animates the escrow steps sequentially with a
 * cascading drop effect.
 */
export function useEscrowFlow() {
  const escrowRef = useRef<HTMLDivElement>(null);
  const hasAnimated = useRef(false);

  useEffect(() => {
    if (!escrowRef.current || hasAnimated.current) return;

    const container = escrowRef.current;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !hasAnimated.current) {
            hasAnimated.current = true;
            animateEscrowSteps(container);
            observer.disconnect();
          }
        });
      },
      { threshold: 0.3 }
    );
    observer.observe(container);

    return () => observer.disconnect();
  }, []);
}

function animateEscrowSteps(container: HTMLDivElement) {
  const steps = container.querySelectorAll('.escrow-step');
  const arrows = container.querySelectorAll('.escrow-arrow');

  anime({
    targets: steps,
    opacity: [0, 1],
    translateY: [-14, 0],
    duration: 450,
    delay: anime.stagger(200, { start: 300 }),
    easing: 'easeOutCubic',
  });

  anime({
    targets: arrows,
    opacity: [0, 1],
    translateY: [-8, 0],
    duration: 300,
    delay: anime.stagger(200, { start: 450 }),
    easing: 'easeOutCubic',
  });
}

/* ------------------------------------------------------------------ */
/*  Agent Grid Animation                                               */
/* ------------------------------------------------------------------ */

/**
 * useAgentGrid — Animates the agent verification items in a grid pattern.
 */
export function useAgentGrid() {
  const gridRef = useRef<HTMLDivElement>(null);
  const hasAnimated = useRef(false);

  useEffect(() => {
    if (!gridRef.current || hasAnimated.current) return;

    const container = gridRef.current;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !hasAnimated.current) {
            hasAnimated.current = true;
            animateAgentGrid(container);
            observer.disconnect();
          }
        });
      },
      { threshold: 0.3 }
    );
    observer.observe(container);

    return () => observer.disconnect();
  }, []);
}

function animateAgentGrid(container: HTMLDivElement) {
  const items = container.querySelectorAll('.agent-item');

  anime({
    targets: items,
    opacity: [0, 1],
    scale: [0.85, 1],
    duration: 400,
    delay: anime.stagger(80, { grid: [2, 3], from: 'center' }),
    easing: 'easeOutBack',
  });
}

/* ------------------------------------------------------------------ */
/*  Floating Particles (subtle background ambiance)                    */
/* ------------------------------------------------------------------ */

/**
 * useHeroParticles — Creates subtle floating particle effect
 * inside the hero section background.
 */
export function useHeroParticles() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || prefersReducedMotion()) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resize = () => {
      const pixelRatio = window.devicePixelRatio || 1;
      const width = Math.max(1, Math.round(canvas.offsetWidth));
      const height = Math.max(1, Math.round(canvas.offsetHeight));

      canvas.width = Math.round(width * pixelRatio);
      canvas.height = Math.round(height * pixelRatio);
      ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    };
    resize();
    window.addEventListener('resize', resize);

    // Create particles
    const particles: Array<{
      x: number;
      y: number;
      size: number;
      speedX: number;
      speedY: number;
      opacity: number;
    }> = [];

    for (let i = 0; i < 20; i++) {
      particles.push({
        x: Math.random() * canvas.offsetWidth,
        y: Math.random() * canvas.offsetHeight,
        size: Math.random() * 3 + 1,
        speedX: (Math.random() - 0.5) * 0.3,
        speedY: -Math.random() * 0.4 - 0.1,
        opacity: Math.random() * 0.3 + 0.05,
      });
    }

    // Animate particles with anime.js
    const animation = anime({
      targets: particles,
      y: () => anime.random(-20, canvas.offsetHeight + 20),
      x: () => anime.random(-20, canvas.offsetWidth + 20),
      opacity: () => Math.random() * 0.3 + 0.05,
      duration: () => anime.random(4000, 8000),
      delay: anime.stagger(200),
      easing: 'easeInOutSine',
      direction: 'alternate',
      loop: true,
      update: () => {
        if (!ctx || !canvas) return;
        ctx.clearRect(0, 0, canvas.offsetWidth, canvas.offsetHeight);
        particles.forEach((p) => {
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(16, 185, 129, ${p.opacity})`;
          ctx.fill();
        });
      },
    });

    return () => {
      animation.pause();
      window.removeEventListener('resize', resize);
    };
  }, []);

  return canvasRef;
}

/* ------------------------------------------------------------------ */
/*  CTA Hover Micro-interaction                                        */
/* ------------------------------------------------------------------ */

/**
 * useCtaHover — Attaches Anime.js hover micro-animations to CTA buttons.
 */
export function useCtaHover() {
  const ctaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ctaRef.current || prefersReducedMotion()) return;
    const buttons = ctaRef.current.querySelectorAll('.hero-cta-btn');

    const handleEnter = (e: Event) => {
      anime({
        targets: e.currentTarget,
        scale: 1.04,
        boxShadow: '0 8px 30px rgba(5, 150, 105, 0.3)',
        duration: 300,
        easing: 'easeOutCubic',
      });
    };

    const handleLeave = (e: Event) => {
      anime({
        targets: e.currentTarget,
        scale: 1,
        boxShadow: '0 4px 14px rgba(5, 150, 105, 0.15)',
        duration: 300,
        easing: 'easeOutCubic',
      });
    };

    buttons.forEach((btn) => {
      btn.addEventListener('mouseenter', handleEnter);
      btn.addEventListener('mouseleave', handleLeave);
    });

    return () => {
      buttons.forEach((btn) => {
        btn.removeEventListener('mouseenter', handleEnter);
        btn.removeEventListener('mouseleave', handleLeave);
      });
    };
  }, []);

  return ctaRef;
}
