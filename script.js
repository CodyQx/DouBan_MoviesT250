const api = '/api'
let page = 1, per_page = 20, totalPages = 1
const moviesEl = document.getElementById('movies')
const searchInput = document.getElementById('search')
const sortSelect = document.getElementById('sort')
const pageInfo = document.getElementById('pageInfo')
const prevBtn = document.getElementById('prev')
const nextBtn = document.getElementById('next')
const wordcloudEl = document.getElementById('wordcloud')
const chartEl = document.getElementById('chart')

async function fetchMovies(){
  const q = new URLSearchParams({page, per_page})
  const search = searchInput.value.trim()
  if(search) q.set('search', search)
  const sort = sortSelect.value
  if(sort) q.set('sort_by', sort)
  const res = await fetch(`${api}/movies?${q.toString()}`)
  const data = await res.json()
  renderMovies(data.items)
  totalPages = data.pages
  pageInfo.textContent = `${data.page} / ${data.pages} （共 ${data.total} 部）`
}

function renderMovies(items){
  moviesEl.innerHTML = ''
  items.forEach(m=>{
    const tpl = document.getElementById('cardTpl')
    const node = tpl.content.cloneNode(true)
    node.querySelector('.title').textContent = m.title
    node.querySelector('.meta').textContent = `${m.year} · ${m.rating || '-'} 分 · ${m.directors}`
    node.querySelector('.tags').textContent = (m.cast||'').split(',').slice(0,3).join(', ')
    const card = node.querySelector('.movie-card')
    card.addEventListener('click', ()=> openDetail(m))
    moviesEl.appendChild(node)
  })
  // load wordcloud for first movie if exists
  if(items.length) loadWordcloud(items[0].id)
}

async function openDetail(m){
  document.getElementById('detailModal').classList.remove('hidden')
  const det = document.getElementById('detail')
  det.innerHTML = `<h2>${m.title} (${m.year})</h2><p>${m.summary || ''}</p><p><strong>导演：</strong>${m.directors}</p><p><strong>演员：</strong>${m.cast}</p>`
  // load comments (前20条)
  const res = await fetch(`${api}/movies/${m.id}/comments?limit=20`)
  const comments = await res.json()
  const ul = document.getElementById('comments')
  ul.innerHTML = ''
  comments.forEach(c=>{
    const li = document.createElement('li')
    li.innerHTML = `<strong>${c.author}</strong> <span class="${ratingClass(c.rating)}">${c.rating||''}</span> <div>${c.content}</div> <div class="meta">${c.date} · 有用 ${c.useful}</div>`
    ul.appendChild(li)
  })
}

document.getElementById('closeDetail').addEventListener('click', ()=>document.getElementById('detailModal').classList.add('hidden'))

document.getElementById('searchBtn').addEventListener('click', ()=>{page=1;fetchMovies()})
prevBtn.addEventListener('click', ()=>{if(page>1)page--;fetchMovies()})
nextBtn.addEventListener('click', ()=>{if(page<totalPages)page++;fetchMovies()})

function ratingClass(r){
  if(!r) return 'rating-low'
  const v = parseFloat(r)
  if(v>8) return 'rating-high'
  if(v>=6) return 'rating-mid'
  return 'rating-low'
}

// Wordcloud using ECharts
let wcChart = echarts.init(wordcloudEl)
async function loadWordcloud(movieId){
  const res = await fetch(`${api}/movies/${movieId}/comments?limit=100`)
  const comments = await res.json()
  const text = comments.map(c=>c.content||'').join('\n')
  const words = tokenize(text)
  const data = Object.entries(freq(words)).map(([name,value])=>({name, value}))
  const option = {
    series: [{
      type: 'wordCloud',
      gridSize: 2,
      sizeRange: [12,50],
      rotationRange: [-90,90],
      textStyle: {color: ()=>['#ff6b6b','#ffa64d','#9aa6b2'][Math.floor(Math.random()*3)]},
      data
    }]
  }
  wcChart.setOption(option)
}

function tokenize(text){
  if(!text) return []
  // naive tokenization: split by non-word chars, filter short tokens
  const raw = text.split(/[^\u4e00-\u9fa5A-Za-z0-9]+/).map(s=>s.trim()).filter(s=>s.length>1)
  return raw
}
function freq(arr){
  const m = {}
  arr.forEach(w=>m[w]= (m[w]||0)+1)
  return m
}

// stats chart on right
let statChart = echarts.init(chartEl)
async function loadStats(){
  const res = await fetch(`${api}/stats`)
  const data = await res.json()
  const rating = data.rating_distribution.map(r=>({name: r.rating, value: r.count}))
  const option = {
    title:{text:'评分分布',left:'center'},
    tooltip:{},
    xAxis:{type:'category',data:rating.map(r=>r.name)},
    yAxis:{},
    series:[{type:'bar',data:rating.map(r=>r.value)}]
  }
  statChart.setOption(option)
}

// initial
fetchMovies(); loadStats();