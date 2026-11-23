document.addEventListener("DOMContentLoaded", () => {

    const menuToggle = document.querySelector(".menu-toggle");
    const headerMenu = document.querySelector("#site-menu");

    if (menuToggle && headerMenu) {
        const closeMenu = () => {
            menuToggle.classList.remove("is-open");
            headerMenu.classList.remove("is-open");
            menuToggle.setAttribute("aria-expanded", "false");
            menuToggle.setAttribute("aria-label", "Открыть меню");
        };

        menuToggle.addEventListener("click", () => {
            const isOpen = menuToggle.getAttribute("aria-expanded") === "true";
            menuToggle.classList.toggle("is-open", !isOpen);
            headerMenu.classList.toggle("is-open", !isOpen);
            menuToggle.setAttribute("aria-expanded", String(!isOpen));
            menuToggle.setAttribute("aria-label", isOpen ? "Открыть меню" : "Закрыть меню");
        });

        headerMenu.querySelectorAll("a").forEach((link) => {
            link.addEventListener("click", closeMenu);
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") closeMenu();
        });

        window.addEventListener("resize", () => {
            if (window.innerWidth > 1024) closeMenu();
        });
    }


    const track = document.querySelector(".slider-track");
    const slides = Array.from(document.querySelectorAll(".slide"));
    const dots = Array.from(document.querySelectorAll(".slider-dot"));
    const previous = document.querySelector(".slider-arrow.prev");
    const next = document.querySelector(".slider-arrow.next");

    if (!track || slides.length === 0) return;

    let activeIndex = 0;
    let timer;

    const showSlide = (index) => {
        activeIndex = (index + slides.length) % slides.length;
        track.style.transform = `translateX(-${activeIndex * 100}%)`;
        dots.forEach((dot, i) => dot.classList.toggle("active", i === activeIndex));
    };

    const restartTimer = () => {
        window.clearInterval(timer);
        timer = window.setInterval(() => showSlide(activeIndex + 1), 5000);
    };

    previous?.addEventListener("click", () => {
        showSlide(activeIndex - 1);
        restartTimer();
    });

    next?.addEventListener("click", () => {
        showSlide(activeIndex + 1);
        restartTimer();
    });

    dots.forEach((dot, index) => {
        dot.addEventListener("click", () => {
            showSlide(index);
            restartTimer();
        });
    });

    showSlide(0);
    restartTimer();
});
