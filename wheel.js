/* Roue du bandeau d'accueil : un clic la fait tourner, puis donne un champion et un rôle au hasard. */
(function(){
  var ROLES = ["Top", "Jungle", "Mid", "ADC", "Support"];
  var DD = {ver: "", list: []}, busy = false, rot = 0;
  var wheel = document.getElementById("heroWheel"), spin = document.getElementById("wheelspin"),
      cta = document.getElementById("wheelCta"), box = document.getElementById("dice");
  if(!wheel || !spin || !box) return;
  var CTA = cta ? cta.textContent : "";

  function load(){
    if(DD.list.length) return Promise.resolve();
    return fetch("https://ddragon.leagueoflegends.com/api/versions.json").then(function(r){ return r.json(); }).then(function(v){
      DD.ver = v[0];
      return fetch("https://ddragon.leagueoflegends.com/cdn/" + DD.ver + "/data/fr_FR/champion.json");
    }).then(function(r){ return r.json(); }).then(function(j){
      DD.list = Object.keys(j.data).map(function(k){ return {id: j.data[k].id, name: j.data[k].name}; });
    });
  }
  function curAngle(){
    var m = getComputedStyle(spin).transform, v = m && m.match(/matrix\(([^)]+)\)/);
    if(!v) return 0;
    var p = v[1].split(",").map(Number);
    return Math.atan2(p[1], p[0]) * 180 / Math.PI;
  }
  function pick(a){ return a[Math.floor(Math.random() * a.length)]; }
  function setCta(t){ if(cta) cta.textContent = t; }

  function show(ch, role){
    document.getElementById("diceImg").src = "https://ddragon.leagueoflegends.com/cdn/" + DD.ver + "/img/champion/" + ch.id + ".png";
    document.getElementById("diceName").textContent = ch.name;
    document.getElementById("diceRole").textContent = role;
    box.hidden = false;
    document.getElementById("diceAgain").focus();
  }
  function close(){ box.hidden = true; wheel.focus(); }

  function go(){
    if(busy) return;
    busy = true; wheel.disabled = true; setCta("Tirage en cours…");
    var start = curAngle();
    spin.style.animation = "none";
    spin.style.transition = "none";
    spin.style.transform = "rotate(" + start + "deg)";
    void spin.getBoundingClientRect();
    rot = start + 360 * (4 + Math.floor(Math.random() * 3)) + Math.random() * 360;
    var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    spin.style.transition = reduce ? "none" : "transform 4.2s cubic-bezier(.12,.62,.1,1)";
    spin.style.transform = "rotate(" + rot + "deg)";
    var ready = load();
    setTimeout(function(){
      ready.then(function(){
        show(pick(DD.list), pick(ROLES));
      }).catch(function(){
        alert("Impossible de charger la liste des champions pour le moment. Réessaie dans un instant.");
      }).then(function(){
        busy = false; wheel.disabled = false; setCta(CTA);
      });
    }, reduce ? 50 : 4400);
  }

  wheel.addEventListener("click", go);
  document.getElementById("diceAgain").addEventListener("click", function(){ box.hidden = true; go(); });
  document.getElementById("diceClose").addEventListener("click", close);
  box.addEventListener("click", function(e){ if(e.target === box) close(); });
  document.addEventListener("keydown", function(e){ if(e.key === "Escape" && !box.hidden) close(); });
  setTimeout(function(){ load().catch(function(){}); }, 1500);
})();
