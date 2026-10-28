// Choix du thème (sombre / éclairé), mémorisé sur cet appareil.
(function(){
  var KEY = "soloq-theme";
  function get(){ try{ return localStorage.getItem(KEY); }catch(e){ return null; } }
  function set(v){ try{ localStorage.setItem(KEY, v); }catch(e){} }
  function apply(t){ document.documentElement.setAttribute("data-theme", t); }
  apply(get() === "light" ? "light" : "dark");
  document.addEventListener("DOMContentLoaded", function(){
    var h = document.querySelector("header"); if(!h) return;
    var b = document.createElement("button"); b.type = "button"; b.className = "themebtn";
    function label(){ var l = document.documentElement.getAttribute("data-theme") === "light"; b.textContent = l ? "🌙 Mode sombre" : "☀️ Mode éclairé"; b.setAttribute("aria-label", l ? "Passer en mode sombre" : "Passer en mode éclairé"); }
    b.addEventListener("click", function(){
      var n = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
      apply(n); set(n); label();
    });
    label(); h.appendChild(b);
  });
})();
