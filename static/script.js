// Animación de entrada para los elementos de la lista
document.addEventListener("DOMContentLoaded", () => {
    const items = document.querySelectorAll(".client-item");

    items.forEach((item, index) => {
        setTimeout(() => {
            item.style.opacity = "1";
            item.style.transform = "translateY(0)";
        }, index * 200); // Retraso progresivo
    });
});

// static/script.js
document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('archivos');
    const previewContainer = document.querySelector('.file-preview');

    fileInput.addEventListener('change', () => {
        previewContainer.innerHTML = '';
        Array.from(fileInput.files).forEach(file => {
            const div = document.createElement('div');
            div.className = 'file-item';
            div.innerHTML = `
                <svg viewBox="0 0 24 24" fill="currentColor">
                    <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
                </svg>
                <span>${file.name}</span>
                <span style="margin-left: auto; color: var(--text-secondary); font-size: 0.8em;">
                    ${(file.size / 1024 / 1024).toFixed(2)} MB
                </span>
            `;
            previewContainer.appendChild(div);
        });
    });
});


// Actualizar al cargar y redimensionar
window.addEventListener('load', updateContainerPadding);
window.addEventListener('resize', updateContainerPadding);