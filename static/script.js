function goTo(path) {
    window.location.href = path;
}

function addToFavorite(title, desc, url) {
    fetch('/tofavorite', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({title, description: desc, url})
    })
    .then(() => {
        document.getElementById('status').textContent = 'Добавлено в избранное!';
        setTimeout(() => {
            document.getElementById('status').textContent = '';
        }, 2000);
    });
}

