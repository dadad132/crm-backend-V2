// PWA Install Prompt Handler
// Only shows the install button on the login page (/web/login).
// On authenticated app pages the button is never displayed so it doesn't
// clutter the desktop UI — users install the app from the login screen.

let deferredPrompt;
let installButton;

const ON_LOGIN_PAGE = window.location.pathname === '/web/login';

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  if (ON_LOGIN_PAGE) {
    showInstallButton();
  }
});

function showInstallButton() {
  if (!ON_LOGIN_PAGE) return;

  if (document.getElementById('pwa-install-button')) {
    document.getElementById('pwa-install-button').style.display = 'flex';
    return;
  }

  installButton = document.createElement('button');
  installButton.id = 'pwa-install-button';
  installButton.innerHTML = `
    <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
    </svg>
    Install App
  `;
  installButton.className = 'fixed bottom-4 right-4 z-50 flex items-center px-4 py-3 bg-gradient-to-r from-red-600 to-red-700 text-white rounded-lg shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105 font-medium';

  installButton.addEventListener('click', async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    console.log(`User response to install prompt: ${outcome}`);
    deferredPrompt = null;
    installButton.style.display = 'none';
  });

  document.body.appendChild(installButton);
}

window.addEventListener('appinstalled', () => {
  console.log('PWA was installed');
  if (installButton) installButton.style.display = 'none';
});

if (
  window.matchMedia('(display-mode: standalone)').matches ||
  window.navigator.standalone === true
) {
  const btn = document.getElementById('pwa-install-button');
  if (btn) btn.style.display = 'none';
}
