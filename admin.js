// Mode admin : 10 clics rapides sur le logo ouvrent un formulaire pour gérer les joueurs, les dates et les photos.
// Les changements sont enregistrés directement dans le dépôt GitHub (players.json, config.json, avatars/) grâce à
// une clé personnelle GitHub que seul l'administrateur possède. Sans cette clé, le formulaire ne peut rien modifier.
(function(){
  var CLICKS = 10, WINDOW_MS = 6000, TOKEN_KEY = "soloq-admin-token";
  var logo = document.querySelector(".logo"); if(!logo) return;

  // ----- ouverture : 10 clics en moins de 6 s -----
  var hits = [];
  logo.addEventListener("click", function(e){
    var now = Date.now(); hits = hits.filter(function(t){return now - t < WINDOW_MS}); hits.push(now);
    if(hits.length >= 2) e.preventDefault();
    if(hits.length >= CLICKS){ hits = []; open(); }
  });

  // ----- dépôt GitHub (déduit de l'adresse du site, sinon valeur par défaut) -----
  var repo = {owner: "dzjdhadbdroid", name: "soloq-challenge"};
  var m = location.hostname.match(/^([^.]+)\.github\.io$/), seg = location.pathname.split("/")[1];
  if(m){ repo.owner = m[1]; if(seg && seg.indexOf(".") < 0) repo.name = seg; }

  function tokenGet(){ try{return localStorage.getItem(TOKEN_KEY)||""}catch(e){return ""} }
  function tokenSet(v){ try{ v ? localStorage.setItem(TOKEN_KEY, v) : localStorage.removeItem(TOKEN_KEY) }catch(e){} }
  function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
  function slug(t){return String(t).normalize("NFKD").replace(/[̀-ͯ]/g,"").toLowerCase().replace(/[^a-z0-9]/g,"")}
  function b64utf8(s){var b = new TextEncoder().encode(s), r = ""; b.forEach(function(x){r += String.fromCharCode(x)}); return btoa(r)}
  function fromB64utf8(b){var r = atob(b.replace(/\s/g,"")), a = new Uint8Array(r.length); for(var i=0;i<r.length;i++) a[i] = r.charCodeAt(i); return new TextDecoder().decode(a)}

  function gh(path, opt){
    opt = opt || {};
    return fetch("https://api.github.com/repos/"+repo.owner+"/"+repo.name+path, {
      method: opt.method || "GET",
      headers: {"Authorization":"Bearer "+tokenGet(), "Accept":"application/vnd.github+json", "X-GitHub-Api-Version":"2022-11-28", "Content-Type":"application/json"},
      body: opt.body ? JSON.stringify(opt.body) : undefined
    }).then(function(r){
      if(r.status === 204) return null;
      return r.json().catch(function(){return {}}).then(function(j){
        if(!r.ok){ var e = new Error(r.status === 401 ? "Clé refusée (expirée ou incorrecte)." : r.status === 403 || r.status === 404 ? "Accès refusé : la clé doit avoir le droit « Contents : Read and write » sur ce dépôt." : r.status === 409 || r.status === 422 ? "Conflit : un autre changement vient d'être enregistré, rouvre le formulaire." : (j.message || "Erreur GitHub "+r.status)); e.status = r.status; throw e; }
        return j;
      });
    });
  }
  function getFile(p){ return gh("/contents/"+p+"?ref=main").then(function(j){return {sha:j.sha, text:fromB64utf8(j.content)}}); }
  function putFile(p, b64, sha, msg){ return gh("/contents/"+p, {method:"PUT", body:{message:msg, content:b64, sha:sha||undefined, branch:"main"}}); }

  // ----- fenêtre -----
  var css = document.createElement("style");
  css.textContent = ".adm-ov{position:fixed;inset:0;z-index:100;background:rgba(30,10,22,.72);display:grid;place-items:center;padding:14px}.adm-ov[hidden]{display:none}"
    + ".adm{background:var(--card);color:var(--txt);border:1px solid var(--line);border-radius:4px;width:min(720px,100%);max-height:calc(100vh - 28px);overflow:auto;padding:22px;font-family:'DM Sans',system-ui,sans-serif}"
    + ".adm h3{font-family:var(--hf,inherit);text-transform:uppercase;font-size:30px;margin:0 0 4px;line-height:1}.adm h4{margin:20px 0 8px;font-size:12px;letter-spacing:1.5px;text-transform:uppercase;color:var(--gold)}"
    + ".adm p,.adm small{color:var(--mut);font-size:13px;line-height:1.5}.adm a{color:var(--gold)}"
    + ".adm input[type=text],.adm input[type=password],.adm input[type=date]{background:var(--bg);color:var(--txt);border:1px solid var(--line);border-radius:3px;padding:10px;font:inherit;font-size:14px;width:100%}"
    + ".adm .row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.adm .row>*{flex:1 1 140px}.adm .row>.fix{flex:none}"
    + ".adm .pl{display:flex;align-items:center;gap:10px;padding:8px 0;border-top:1px solid var(--line)}.adm .pl img,.adm .pl .ph{width:38px;height:38px;border-radius:50%;object-fit:cover;background:var(--card2);flex:none;display:grid;place-items:center;font-weight:800}"
    + ".adm .pl .n{flex:1;min-width:0}.adm .pl .n b{display:block}.adm .pl.rm .n{text-decoration:line-through;opacity:.5}"
    + ".adm button{font:700 12px 'DM Sans',system-ui,sans-serif;letter-spacing:.6px;text-transform:uppercase;border-radius:3px;padding:10px 14px;cursor:pointer;border:1px solid var(--line);background:var(--card2);color:var(--txt)}"
    + ".adm button.pri{background:var(--wb,#641d32);color:#fff;border-color:transparent}.adm button.dng{color:var(--loss)}.adm button:disabled{opacity:.5;cursor:default}"
    + ".adm .msg{margin-top:12px;padding:10px 12px;border-radius:3px;font-size:13px;background:var(--card2)}.adm .msg.err{color:var(--loss)}.adm .msg.ok{color:var(--win)}.adm ol{padding-left:18px;margin:8px 0}";
  document.head.appendChild(css);
  var ov = document.createElement("div"); ov.className = "adm-ov"; ov.hidden = true;
  ov.innerHTML = '<div class="adm" role="dialog" aria-modal="true" aria-label="Mode admin"></div>';
  document.body.appendChild(ov);
  var box = ov.firstChild, S = null;
  ov.addEventListener("click", function(e){ if(e.target === ov) close(); });
  document.addEventListener("keydown", function(e){ if(e.key === "Escape" && !ov.hidden) close(); });
  function close(){ ov.hidden = true; }
  function msg(t, kind){ var m = box.querySelector(".msg"); if(m){ m.className = "msg "+(kind||""); m.textContent = t; m.hidden = !t; } }

  function open(){ ov.hidden = false; tokenGet() ? connect() : renderLogin(); }

  function renderLogin(err){
    box.innerHTML = '<h3>Mode admin</h3><p>Pour modifier le site sans toucher aux fichiers, colle ta clé personnelle GitHub. Elle reste dans ce navigateur uniquement.</p>'
      + '<details><summary style="cursor:pointer;color:var(--gold)">Comment obtenir la clé ?</summary><ol><li>Ouvre <a target="_blank" rel="noopener" href="https://github.com/settings/personal-access-tokens/new">github.com/settings/personal-access-tokens/new</a></li>'
      + '<li>Nom : <i>soloq-admin</i> · Expiration : à ta convenance (ex. 90 jours).</li><li><b>Repository access</b> → « Only select repositories » → <b>'+esc(repo.name)+'</b>.</li>'
      + '<li><b>Permissions</b> → Repository permissions → <b>Contents : Read and write</b>.</li><li>« Generate token », copie la clé (elle commence par <code>github_pat_</code>) et colle-la ci-dessous.</li></ol></details>'
      + '<h4>Clé GitHub</h4><input type="password" id="adm-tok" autocomplete="off" placeholder="github_pat_…"><div class="row" style="margin-top:12px"><button class="pri fix" id="adm-go">Se connecter</button><button class="fix" id="adm-x">Fermer</button></div><div class="msg err" '+(err?'':'hidden')+'>'+esc(err||"")+'</div>';
    box.querySelector("#adm-x").onclick = close;
    box.querySelector("#adm-go").onclick = function(){ var v = box.querySelector("#adm-tok").value.trim(); if(!v) return; tokenSet(v); connect(); };
  }

  function connect(){
    box.innerHTML = '<h3>Mode admin</h3><p>Connexion à GitHub…</p>';
    Promise.all([gh(""), getFile("players.json"), getFile("config.json").catch(function(){return null}),
                 gh("/contents/avatars?ref=main").catch(function(){return []})]).then(function(r){
      if(r[0].permissions && r[0].permissions.push === false) throw new Error("Cette clé n'a pas le droit d'écrire dans le dépôt.");
      var players; try{ players = JSON.parse(r[1].text); }catch(e){ throw new Error("players.json est invalide : corrige-le d'abord sur GitHub."); }
      var cfg = {}; if(r[2]){ try{ cfg = JSON.parse(r[2].text); }catch(e){} }
      S = {players: players, orig: JSON.stringify(players), playersSha: r[1].sha, cfg: cfg, origCfg: JSON.stringify(cfg), cfgSha: r[2] && r[2].sha,
           avatars: Array.isArray(r[3]) ? r[3] : [], removed: {}, photos: {}};
      render();
    }).catch(function(e){ if(e.status === 401 || e.status === 403 || e.status === 404){ tokenSet(""); renderLogin(e.message); } else renderLogin(e.message); });
  }

  function thumb(p){
    var a = S.photos[p.riot] ? S.photos[p.riot].url : null;
    if(!a){ var f = S.avatars.filter(function(x){return slug(x.name.replace(/\.[^.]+$/,"")) === slug(p.name)})[0]; if(f) a = f.download_url; }
    return a ? '<img alt="" src="'+esc(a)+'">' : '<span class="ph">'+esc(String(p.name).slice(0,1).toUpperCase())+'</span>';
  }

  function render(){
    var e1 = box.querySelector("#adm-d1"), e2 = box.querySelector("#adm-d2");   // garde les dates en cours de saisie
    if(e1 && e2){ S.draft = {start: e1.value, end: e2.value}; }
    var keepMsg = box.querySelector(".msg") ? box.querySelector(".msg").outerHTML : "";
    box.innerHTML = '<div class="row" style="align-items:flex-start"><div><h3>Mode admin</h3><small>'+esc(repo.owner+"/"+repo.name)+'</small></div><button class="fix" id="adm-out">Déconnecter</button></div>'
      + '<h4>Joueurs ('+S.players.filter(function(p){return !S.removed[p.riot]}).length+'/20)</h4><div id="adm-list">'
      + S.players.map(function(p,i){
          return '<div class="pl'+(S.removed[p.riot]?" rm":"")+'">'+thumb(p)+'<div class="n"><b>'+esc(p.name||"")+'</b><small>'+esc(p.riot||"")+'</small></div>'
            + '<button data-ph="'+i+'">Photo</button><button class="dng" data-rm="'+i+'">'+(S.removed[p.riot]?"Annuler":"Retirer")+'</button></div>';
        }).join("") + '</div>'
      + '<h4>Ajouter un joueur</h4><div class="row"><input type="text" id="adm-name" placeholder="Prénom affiché (ex. Kuro)"><input type="text" id="adm-riot" placeholder="Pseudo#TAG (ex. Kuro#EUW)"><button class="fix" id="adm-add">Ajouter</button></div>'
      + '<h4>Dates du challenge</h4><div class="row"><label>Début<input type="date" id="adm-d1" value="'+esc((S.draft&&S.draft.start)||S.cfg.start||"")+'"></label><label>Fin<input type="date" id="adm-d2" value="'+esc((S.draft&&S.draft.end)||S.cfg.end||"")+'"></label></div>'
      + '<div class="row" style="margin-top:20px"><button class="pri fix" id="adm-save">Enregistrer les changements</button><button class="fix" id="adm-x">Fermer</button></div>'
      + (keepMsg || '<div class="msg" hidden></div>')
      + '<input type="file" id="adm-file" accept="image/*" hidden>';
    box.querySelector("#adm-x").onclick = close;
    box.querySelector("#adm-out").onclick = function(){ tokenSet(""); S = null; renderLogin(); };
    box.querySelectorAll("[data-rm]").forEach(function(b){ b.onclick = function(){ var p = S.players[+b.dataset.rm]; S.removed[p.riot] = !S.removed[p.riot]; render(); }; });
    var fileIn = box.querySelector("#adm-file"), target = null;
    box.querySelectorAll("[data-ph]").forEach(function(b){ b.onclick = function(){ target = S.players[+b.dataset.ph]; fileIn.value = ""; fileIn.click(); }; });
    fileIn.onchange = function(){ if(fileIn.files[0] && target) prepPhoto(fileIn.files[0], target); };
    box.querySelector("#adm-add").onclick = addPlayer;
    box.querySelector("#adm-save").onclick = save;
  }

  function addPlayer(){
    var n = box.querySelector("#adm-name").value.trim(), r = box.querySelector("#adm-riot").value.trim();
    if(!n || r.indexOf("#") < 1 || r.split("#")[1].length < 2) return msg("Renseigne un prénom et un Riot ID au format Pseudo#TAG.", "err");
    if(S.players.some(function(p){return String(p.riot).toLowerCase() === r.toLowerCase()})) return msg("Ce joueur est déjà dans la liste.", "err");
    if(S.players.filter(function(p){return !S.removed[p.riot]}).length >= 20) return msg("20 joueurs maximum.", "err");
    S.players.push({name: n, riot: r}); render(); msg("Ajouté dans la liste : clique sur « Enregistrer » pour l'envoyer au site.", "ok");
  }

  // photo : recadrée en carré 256 px, compressée en JPEG (largement sous 1 Mo)
  function prepPhoto(file, p){
    var img = new Image(), url = URL.createObjectURL(file);
    img.onload = function(){
      var c = document.createElement("canvas"); c.width = c.height = 256; var x = c.getContext("2d"), s = Math.min(img.width, img.height);
      x.drawImage(img, (img.width-s)/2, (img.height-s)/2, s, s, 0, 0, 256, 256); URL.revokeObjectURL(url);
      c.toBlob(function(b){
        var fr = new FileReader(); fr.onload = function(){ S.photos[p.riot] = {b64: String(fr.result).split(",")[1], url: fr.result}; render(); msg("Photo prête pour "+p.name+" : clique sur « Enregistrer ».", "ok"); }; fr.readAsDataURL(b);
      }, "image/jpeg", .86);
    };
    img.onerror = function(){ msg("Image illisible.", "err"); }; img.src = url;
  }

  function save(){
    var btn = box.querySelector("#adm-save"); btn.disabled = true; msg("Enregistrement…");
    var d1 = box.querySelector("#adm-d1").value, d2 = box.querySelector("#adm-d2").value;
    if(d1 && d2 && d2 < d1){ btn.disabled = false; return msg("La date de fin est avant la date de début.", "err"); }
    var list = S.players.filter(function(p){return !S.removed[p.riot]}).map(function(p){return Object.assign({}, p)});
    var cfg = Object.assign({}, S.cfg); if(d1) cfg.start = d1; if(d2) cfg.end = d2;
    var chain = Promise.resolve(), changed = [];
    list.forEach(function(p){
      var ph = S.photos[p.riot]; if(!ph) return;
      var path = "avatars/"+(slug(p.name) || "joueur")+".jpg", ex = S.avatars.filter(function(a){return a.path === path})[0];
      p.avatar = path;
      chain = chain.then(function(){ return putFile(path, ph.b64, ex && ex.sha, "Admin : photo de "+p.name); }).then(function(r){ changed.push("photo de "+p.name); if(r && r.content) S.avatars.push({name: r.content.name, path: path, sha: r.content.sha}); });
    });
    var pj = JSON.stringify(list, null, 2) + "\n";
    if(JSON.stringify(list) !== S.orig || list.some(function(p){return p.avatar})){
      chain = chain.then(function(){ return putFile("players.json", b64utf8(pj), S.playersSha, "Admin : liste des joueurs"); }).then(function(r){ S.playersSha = r.content.sha; changed.push("joueurs"); });
    }
    if(JSON.stringify(cfg) !== S.origCfg){
      chain = chain.then(function(){ return putFile("config.json", b64utf8(JSON.stringify(cfg)+"\n"), S.cfgSha, "Admin : dates du challenge"); }).then(function(r){ S.cfgSha = r.content.sha; changed.push("dates"); });
    }
    chain.then(function(){
      S.players = list; S.orig = JSON.stringify(list); S.cfg = cfg; S.origCfg = JSON.stringify(cfg); S.removed = {}; S.photos = {}; S.draft = null;
      render();
      msg(changed.length ? "Enregistré ("+changed.join(", ")+"). Le site se met à jour d'ici 1 à 3 minutes." : "Rien n'a changé.", changed.length ? "ok" : "");
    }).catch(function(e){ var b = box.querySelector("#adm-save"); if(b) b.disabled = false; msg(e.message, "err"); });
  }
})();
