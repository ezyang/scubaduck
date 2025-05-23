// Sidebar resizing logic extracted from index.html

const sidebar = document.getElementById('sidebar');
const sidebarResizer = document.getElementById('sidebar-resizer');
let sidebarWidth = parseInt(localStorage.getItem('sidebarWidth') || 450, 10);
sidebar.style.width = sidebarWidth + 'px';
let sidebarResize = false;

function startSidebarDrag(e) {
  e.preventDefault();
  sidebarResize = true;
  document.addEventListener('mousemove', onSidebarDrag);
  document.addEventListener('mouseup', stopSidebarDrag);
}

function onSidebarDrag(e) {
  if (!sidebarResize) return;
  sidebarWidth = Math.max(200, e.clientX - sidebar.getBoundingClientRect().left);
  sidebar.style.width = sidebarWidth + 'px';
}

function stopSidebarDrag() {
  document.removeEventListener('mousemove', onSidebarDrag);
  document.removeEventListener('mouseup', stopSidebarDrag);
  sidebarResize = false;
  localStorage.setItem('sidebarWidth', sidebarWidth);
}

sidebarResizer.addEventListener('mousedown', startSidebarDrag);

