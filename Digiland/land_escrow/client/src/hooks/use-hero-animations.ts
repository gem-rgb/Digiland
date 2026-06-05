/**
 * useHeroAnimations — Anime.js-powered hero section animation controller.
 *
 * Provides React hooks that orchestrate all hero section animations using
 * Anime.js timelines, staggered reveals, and looping scene transitions.
 * Replaces the previous CSS-only animation approach with a more expressive,
 * choreographed motion system.
 */
import { useEffect, useRef, useCallback } from 'react';
import anime from 'animejs';

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
    if (!heroRef.current || hasPlayed.current) return;
    hasPlayed.current = true;

    const hero = heroRef.current;

    // ── Left side: staggered reveal ──
    const leftItems = hero.querySelectorAll('.hero-entrance-item');
    anime({
      targets: leftItems,
      opacity: [0, 1],
      translateY: [28, 0],
      duration: 700,
      delay: anime.stagger(120, { start: 200 }),
      easing: 'easeOutCubic',
    });

    // ── Badge: special pop-in ──
    const badge = hero.querySelector('.hero-badge');
    if (badge) {
      anime({
        targets: badge,
        opacity: [0, 1],
        scale: [0.6, 1],
        duration: 500,
        delay: 100,
        easing: 'easeOutBack',
      });
    }

    // ── Headline: character-by-character shimmer ──
    const headline = hero.querySelector('.hero-headline');
    if (headline) {
      anime({
        targets: headline,
        opacity: [0, 1],
        clipPath: ['inset(0 100% 0 0)', 'inset(0 0% 0 0)'],
        duration: 900,
        delay: 350,
        easing: 'easeInOutQuart',
      });
    }

    // ── Trust indicators: stagger from left ──
    const trustItems = hero.querySelectorAll('.hero-trust-item');
    anime({
      targets: trustItems,
      opacity: [0, 1],
      translateX: [-16, 0],
      duration: 500,
      delay: anime.stagger(80, { start: 1100 }),
      easing: 'easeOutCubic',
    });

    // ── Right side: cards fly in ──
    const rightCards = hero.querySelectorAll('.hero-right-card');
    anime({
      targets: rightCards,
      opacity: [0, 1],
      translateX: [40, 0],
      scale: [0.95, 1],
      duration: 600,
      delay: anime.stagger(150, { start: 500 }),
      easing: 'easeOutCubic',
    });

    // ── Stat cards: count-up shimmer ──
    const statCards = hero.querySelectorAll('.hero-stat-card');
    anime({
      targets: statCards,
      opacity: [0, 1],
      translateY: [16, 0],
      scale: [0.92, 1],
      duration: 500,
      delay: anime.stagger(100, { start: 1300 }),
      easing: 'easeOutCubic',
    });
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

// We need useState for the cycler hook
import { useState } from 'react';

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
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resize = () => {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio;
      canvas.height = canvas.offsetHeight * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
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
    if (!ctaRef.current) return;
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
