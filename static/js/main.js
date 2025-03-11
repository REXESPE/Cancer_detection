async function takePhoto() {
    try {
        // Deshabilitar el botón mientras se procesa
        const button = document.getElementById('photoButton');
        button.disabled = true;

        const response = await fetch('/take-photo', { method: 'GET' });
        if (response.ok) {
            const result = await response.json();
            showNotification('Foto tomada y PDF generado con éxito');
            window.open('/download-pdf'+ result.id, '_blank');
        } else {
            const error = await response.json();
            showNotification(error.error || 'Error al procesar la imagen', 'error');
        }
    } catch (error) {
        showNotification('Error de conexión', 'error');
        console.error('Error:', error);
    } finally {
        // Restaurar el estado del botón
        updateButtonState();
    }
}

// Función para mostrar notificaciones
function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.textContent = message;
    notification.className = `notification ${type}`;

    document.body.appendChild(notification);

    // Animar la salida y remover después de un tiempo
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.5s ease-out';
        setTimeout(() => notification.remove(), 500);
    }, 3000);
}

// Función para actualizar el estado del botón
async function updateButtonState() {
    try {
        const response = await fetch('/detection-status');
        const data = await response.json();
        const button = document.getElementById('photoButton');

        button.disabled = !data.detected;
        button.title = data.detected ?
            'Tomar foto y generar informe' :
            'Esperando detección de cáncer de piel';

        // Actualizar clase de estado
        button.className = data.detected ? 'active' : '';
    } catch (error) {
        console.error('Error al verificar el estado de detección:', error);
    }
}

// Función para inicializar la aplicación
function initApp() {
    // Comprobar el estado de detección periódicamente
    setInterval(updateButtonState, 1000);

    // Primera comprobación inmediata
    updateButtonState();

    // Agregar event listener para el botón
    const button = document.getElementById('photoButton');
    button.addEventListener('click', takePhoto);
}

// Iniciar la aplicación cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', initApp);