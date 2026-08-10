const state={products:[],lang:localStorage.getItem("lang")||"fr",theme:localStorage.getItem("theme")||"dark",category:"all",query:""};
const $=s=>document.querySelector(s), $$=s=>document.querySelectorAll(s);
const t={
 fr:{
  search:"Rechercher un vêtement...",popular:"Populaire",empty:"Aucun vêtement ne correspond à ta recherche.",
  buy:"Acheter / Voir le produit",all:"Tout",sizes:"Taille(s)",styles:"Styles",weight:"Poids",dimensions:"Dimensions",
  seller:"Vendeur",reference:"Référence",season:"Saison",channel:"Plateforme",productPhotos:"Photos produit",qcPhotos:"Photos QC",noDescription:"Aucune description."
 },
 en:{
  search:"Search for clothing...",popular:"Popular",empty:"No items match your search.",
  buy:"Buy / View product",all:"All",sizes:"Size(s)",styles:"Styles",weight:"Weight",dimensions:"Dimensions",
  seller:"Seller",reference:"Reference",season:"Season",channel:"Platform",productPhotos:"Product photos",qcPhotos:"QC photos",noDescription:"No description."
 }
};
function esc(v){return String(v??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));}
function money(v,c="EUR"){if(v==null||v==="")return "—";const n=Number(String(v).replace(",","."));return Number.isFinite(n)?new Intl.NumberFormat(state.lang,{style:"currency",currency:c}).format(n):esc(v);}
function productImages(p){return (p.productImages&&p.productImages.length?p.productImages:p.images)||[];}
function qcImages(p){return p.qcImages||[];}
function img(p){return productImages(p)[0]||p.image||"https://via.placeholder.com/600x750/1e1e1e/666?text=Photo";}
function normalizeCategory(c){const x=String(c||"").toLowerCase();if(["tshirt","t-shirt","t-shirts","tee"].some(a=>x.includes(a)))return"tshirt";if(x.includes("veste")||x.includes("jacket"))return"veste";if(x.includes("pantalon")||x.includes("pants")||x.includes("sweat"))return"pantalon";if(x.includes("chauss")||x.includes("shoe"))return"chaussure";if(x.includes("sac")||x.includes("bag"))return"sac";return"accessoire";}
function renderGallery(images,activeSrc){
 const list=images.length?images:[activeSrc].filter(Boolean);
 $("#galleryMain").src=list[0]||"";
 $("#thumbs").innerHTML=list.map(x=>`<img src="${esc(x)}" alt="" loading="lazy" class="${x===activeSrc?"active":""}">`).join("");
 $$("#thumbs img").forEach(x=>x.onclick=()=>{$("#galleryMain").src=x.src;$$("#thumbs img").forEach(i=>i.classList.toggle("active",i===x));});
}
function render(){
 const q=state.query.toLowerCase(); const list=state.products.filter(p=>{const cat=normalizeCategory(p.category);const text=[p.name,p.title,p.description,p.seller,p.channel,...(p.tags||[]),...(p.styles||[]),...(p.sizes||[])].join(" ").toLowerCase();return(state.category==="all"||cat===state.category)&&(!q||text.includes(q));});
 $("#productGrid").innerHTML=list.map(p=>`<article class="card"><img src="${esc(img(p))}" alt="${esc(p.name||p.title||"Produit")}" loading="lazy"><div class="card-info"><h2>${esc(p.name||p.title||"Produit")}</h2><p class="price">${money(p.price,p.currency||"EUR")}</p><button class="link-btn" data-id="${esc(p.id)}">${esc(t[state.lang].buy)}</button></div></article>`).join("");
 $("#emptyMsg").style.display=list.length?"none":"block"; $("#sectionTitle").textContent=t[state.lang].popular;
 $$("#productGrid .link-btn").forEach(b=>b.onclick=()=>openProduct(state.products.find(p=>String(p.id)===b.dataset.id)));
}
function openProduct(p){
 $("#modalTitle").textContent=p.name||p.title||"Produit";$("#modalPrice").textContent=money(p.price,p.currency||"EUR");$("#modalDescription").textContent=p.description||t[state.lang].noDescription;
 const meta=[[t[state.lang].sizes,(p.sizes||[]).join(", ")],[t[state.lang].styles,(p.styles||[]).join(", ")],[t[state.lang].weight,p.weight],[t[state.lang].dimensions,p.dimensions],[t[state.lang].season,p.season],[t[state.lang].channel,p.channel],[t[state.lang].seller,p.seller],[t[state.lang].reference,p.sku||p.id]].filter(x=>x[1]);
 $("#modalMeta").innerHTML=meta.map(x=>`<div><small>${esc(x[0])}</small>${esc(x[1])}</div>`).join("");
 $("#modalTags").innerHTML=(p.tags||[]).map(x=>`<span class="tag">${esc(x)}</span>`).join("");
 const photos=productImages(p), qc=qcImages(p);
 $$(".gallery-tab").forEach(tab=>{const mode=tab.dataset.gallery;tab.classList.toggle("active",mode==="product");tab.onclick=()=>{$$(".gallery-tab").forEach(x=>x.classList.remove("active"));tab.classList.add("active");renderGallery(mode==="qc"?qc:photos);};});
 renderGallery(photos);
 $("#buyBtn").href=p.buyUrl||p.sourceUrl||"#";$("#buyBtn").textContent=t[state.lang].buy;
 $("#productModal").classList.add("open");
}
async function load(){try{const r=await fetch("data/products.json",{cache:"no-store"});if(!r.ok)throw new Error("products.json introuvable");state.products=await r.json();render();}catch(e){console.error(e);$("#emptyMsg").textContent="Impossible de charger les produits. Vérifie data/products.json.";$("#emptyMsg").style.display="block";}}
function apply(){document.documentElement.dataset.theme=state.theme;localStorage.setItem("theme",state.theme);$("#searchInput").placeholder=t[state.lang].search;$$("[data-lang-choice]").forEach(b=>b.classList.toggle("active",b.dataset.langChoice===state.lang));$$("[data-theme-choice]").forEach(b=>b.classList.toggle("active",b.dataset.themeChoice===state.theme));render();}
$("#searchInput").oninput=e=>{state.query=e.target.value;render()};
$$(".category").forEach(b=>b.onclick=()=>{$$(".category").forEach(x=>x.classList.remove("active"));b.classList.add("active");state.category=b.dataset.category;render()});
$("#profileBtn").onclick=e=>{e.stopPropagation();$("#profileDropdown").classList.toggle("open")};document.addEventListener("click",()=>$("#profileDropdown").classList.remove("open"));
$$("[data-theme-choice]").forEach(b=>b.onclick=()=>{state.theme=b.dataset.themeChoice;apply()});
$$("[data-lang-choice]").forEach(b=>b.onclick=()=>{state.lang=b.dataset.langChoice;localStorage.setItem("lang",state.lang);apply()});
$("#closeModal").onclick=()=>$("#productModal").classList.remove("open");$("#productModal").onclick=e=>{if(e.target.id==="productModal")$("#productModal").classList.remove("open")};
apply();load();
