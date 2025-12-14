let randomProfile = [
    'https://i.pinimg.com/736x/8f/84/36/8f84360a1a40c8969e0942eeecb587aa.jpg',
    'https://i.pinimg.com/736x/be/cb/20/becb20c5c553b02592eb50efb08c2e5e.jpg',
    'https://i.pinimg.com/736x/38/61/6f/38616f4a0f45ba196a176620cd564e87.jpg',
    'https://i.pinimg.com/736x/f9/c3/db/f9c3db06ef9dee6428f38332c6fbd3bb.jpg',
    'https://i.pinimg.com/1200x/6f/46/35/6f46355eb649ab34f667c040b35bf79d.jpg',
    'https://i.pinimg.com/736x/94/e4/b8/94e4b8ac4a8b734ab93a55369354649c.jpg'
]

const DEFAULT_POSTER = "https://upload.wikimedia.org/wikipedia/en/thumb/3/3f/The_Empire_Strikes_Back_%281980_film%29.jpg/250px-The_Empire_Strikes_Back_%281980_film%29.jpg";

document.addEventListener('DOMContentLoaded', () => {
    updateNavbar();
});

function randomNumber(min, max){
    min = Math.ceil(min);
    max = Math.floor(max);
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

function checkSignIn(){
    const userId = sessionStorage.getItem('user_id');
    if(!userId) return false;
    else return true;
}

function updateNavbar() {
    // 檢查 sessionStorage 是否有使用者 ID
    const userId = sessionStorage.getItem('user_id');
    const authLink = document.getElementById('auth_link') || document.querySelector('a[href="sign_in.html"]');

    if (!authLink) return;

    if (userId) {
        // 已登入狀態
        authLink.textContent = "Profile";     
        authLink.href = "user.html";         
        
        authLink.classList.remove('bg-gray-600', 'hover:bg-gray-500');
        authLink.classList.add('bg-blue-950', 'hover:bg-blue-900');
    } else {
        // 未登入狀態 
        authLink.textContent = "Sign In";
        authLink.href = "sign_in.html";
        
        authLink.classList.remove('bg-blue-950', 'hover:bg-blue-900');
        authLink.classList.add('bg-gray-600', 'hover:bg-gray-500');
    }
}

function showAlert(type, message) {
    alert_box.textContent = message;

    //success green ; failed red
    if (type === 'success') alert_box.className = "px-4 py-2 rounded-xl shadow-lg text-sm font-medium bg-green-600 text-white";
    else alert_box.className = "px-4 py-2 rounded-xl shadow-lg text-sm font-medium bg-red-600 text-white";

    // 顯示
    alert_wrapper.classList.remove("opacity-0", "-translate-y-4");
    alert_wrapper.classList.add("opacity-100", "translate-y-0");

    // 幾秒後自動關閉
    setTimeout(() => {
        alert_wrapper.classList.add("opacity-0", "-translate-y-4");
        alert_wrapper.classList.remove("opacity-100", "translate-y-0");
    }, 3000);
}

document.addEventListener('DOMContentLoaded', () => {
    updateNavbar();

    const navSearch = document.getElementById('nav_search'); 
    const navInput = document.getElementById('nav_keyword');
    const navType = document.getElementById('nav_type');
    const container = document.getElementById('results_container');
    const searchTitle = document.getElementById('search_title');
    
    const API_BASE = 'http://127.0.0.1:8000';

    function triggerSearch() {
        const keyword = navInput.value.trim();
        const type = navType.value;

        if (!keyword) {
            showAlert('failed', "Please enter a keyword");
            return;
        }

        const targetUrl = `nav_search_result.html?name=${encodeURIComponent(keyword)}&type=${type}`;
        window.location.href = targetUrl;
    }

    if (navSearch) {
        navSearch.addEventListener('click', (e) => {
            e.preventDefault();
            triggerSearch();
        });
    }

    if (navInput) {
        navInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                triggerSearch();
            }
        });
    }

    async function loadSearchResults() {
        if (!container) return;

        const params = new URLSearchParams(window.location.search);
        const keyword = params.get('name'); 
        const type = params.get('type') || 'all'; 

        if (!keyword) return;

        if (navInput) navInput.value = keyword;
        if (navType) navType.value = type;

        // 顯示 Loading
        container.innerHTML = '<p class="text-center text-gray-500 mt-10">Searching...</p>';
        if (searchTitle) searchTitle.classList.remove('hidden');

        try {
            const res = await fetch(`${API_BASE}/nav?name=${keyword}&type=${type}`);
            if (!res.ok) throw new Error("Search failed");
            
            const data = await res.json();
            renderNavResults(data);

        } catch (error) {
            console.error(error);
            container.innerHTML = '<p class="text-center text-red-500 mt-10">An error occurred while searching.</p>';
        }
    }

    loadSearchResults();

    function renderNavResults(data) {
        container.innerHTML = ''; 
        let hasData = false;
        const batchSize = 20;

        const sections = [
            { key: 'movie_list', title: 'Movies', render: renderMovieCard },
            { key: 'actor_list', title: 'Actors', render: renderActorCard },
            { key: 'director_list', title: 'Directors', render: renderDirectorCard },
            { key: 'company_list', title: 'Companies', render: renderCompanyCard },
            { key: 'user_list', title: 'Users', render: renderUserCard },
            { key: 'genre_list', title: 'Genres', render: renderSimpleCard },
            { key: 'role_list', title: 'Roles', render: renderSimpleCard },
        ];

        sections.forEach(section => {
            const list = data[section.key];
            if (list && list.length > 0) {
                hasData = true;
                const sectionDiv = document.createElement('section');
                sectionDiv.innerHTML = `
                    <div class="flex w-full justify-between">
                        <h2 class="text-2xl font-bold mb-4 text-gray-800">${section.title} </h2>
                        <span class="text-lg mb-4 text-gray-800">${list.length} results</span>
                    </div>                   
                    
                    <div class="result-grid grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-6">
                    </div>
                    <div class="show-more-container mt-4 flex justify-center">
                        <button type="button" id="show_more" class="text-gray-500 hover:text-gray-700 flex items-center text-sm">
                            Show more ${section.title}
                            <svg class="w-4 h-4 ml-1 animate-bounce" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                    d="M19 9l-7 7-7-7" />
                            </svg>
                        </button>
                    </div>
                    <hr class="mt-8 border-gray-200"/>
                `;

                const gridContainer = sectionDiv.querySelector('.result-grid');
                const showMoreContainer = sectionDiv.querySelector('.show-more-container');
                const showMoreBtn = showMoreContainer ? showMoreContainer.querySelector('button') : null;

                let currentCount = 0;

                const loadMoreItems = () => {
                    const nextBatch = list.slice(currentCount, currentCount + batchSize);
                    
                    // 產生 HTML並插入Grid
                    const batchHTML = nextBatch.map(item => section.render(item)).join('');
                    gridContainer.insertAdjacentHTML('beforeend', batchHTML);

                    // 更新計數
                    currentCount += nextBatch.length;

                    // 檢查是否還有剩餘資料
                    if (currentCount >= list.length) {
                        showMoreContainer.classList.add('hidden');
                    } else {
                        showMoreContainer.classList.remove('hidden');
                    }
                };

                if (showMoreBtn) {
                    showMoreBtn.addEventListener('click', (e) => {
                        e.preventDefault(); 
                        loadMoreItems();
                    });
                }

                loadMoreItems();

                container.appendChild(sectionDiv);
            }
        });

        if (!hasData) {
            container.innerHTML = '<p class="text-center text-gray-500 mt-10 text-xl">No results found.</p>';
        }
    }

    function renderMovieCard(m) {
    const posterUrl = m.poster_url || DEFAULT_POSTER;

    return `
        <div class="bg-gray-50 p-4 rounded-lg shadow hover:shadow-md transition border border-gray-200 flex flex-col items-center text-center">
            <a href="movie.html?movie_id=${m.movie_id}" class="w-full mb-2">
                <img
                    src="${posterUrl}"
                    alt="${m.title}"
                    class="w-full h-40 md:h-48 object-cover rounded"
                />
            </a>
            <a href="movie.html?movie_id=${m.movie_id}" class="font-bold text-lg leading-tight mb-1 hover:text-gray-700">
                ${m.title}
            </a>
            <p class="text-sm text-gray-600">${m.release_year || 'N/A'}</p>
            <p class="text-xs text-gray-500 mt-1">${m.country || ''}</p>
        </div>
    `;
}

    function renderActorCard(a) {a
        return `
            <div class="bg-white p-4 rounded-lg shadow hover:shadow-xl transition border border-gray-300">
                <a href = actor.html?actor_id=${a.actor_id} class="font-bold text-lg hover:text-gray-700">${a.name}</a>
                <p class="text-sm text-gray-600">Birth: ${a.birth_year || 'N/A'}</p>
                <p class="text-sm text-gray-600">Nation: ${a.nationality || 'N/A'}</p>
            </div>
        `;
    }

    function renderDirectorCard(p) {
        return `
            <div class="bg-white p-4 rounded-lg shadow hover:shadow-xl transition border border-gray-300">
                <h3 class="font-bold text-lg">${p.name}</h3>
                <p class="text-sm text-gray-600">Birth: ${p.birth_year || 'N/A'}</p>
                <p class="text-sm text-gray-600">Nation: ${p.nationality || 'N/A'}</p>
            </div>
        `;
    }

    function renderCompanyCard(c) {
        return `
            <div class="bg-white p-4 rounded-lg shadow hover:shadow-xl transition border border-gray-300">
                <a href = company.html?company_id=${c.company_id} class="font-bold text-lg hover:text-gray-700">${c.name}</a>
                <p class="text-sm text-gray-600">Est. ${c.founded_year || 'N/A'}</p>
                <p class="text-xs text-gray-500">${c.country || ''}</p>
            </div>
        `;
    }

    function renderUserCard(u) {
        const randomImg = randomProfile[randomNumber(0, 5)];

        return `
            <div class="bg-white p-4 rounded-lg shadow hover:shadow-xl transition border border-gray-300 flex items-center space-x-3">
                <img src=${randomImg} class="w-10 h-10 rounded-full bg-gray-300 flex-shrink-0"></img>
                <div>
                    <a href = user.html?user_id=${u.user_id} class="font-bold text-lg leading-tight mb-1 hover:text-gray-700">${u.name}</a>
                    <p class="text-xs text-gray-500">Age: ${u.age || '?'}</p>
                </div>
            </div>
        `;
    }

    function renderSimpleCard(item) {
        return `
            <div class="bg-gray-100 border-gray-300 p-3 rounded-lg text-center hover:hover:shadow-xl transition">
                <span class="font-medium text-lg">${item.name}</span>
            </div>
        `;
    }
});