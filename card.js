// Carte joueur : image PNG générée dans le navigateur (aucun serveur), à télécharger ou partager.
var CARD_RIOT = null;
(function(){
  var W = 800, H = 1120;
  var st = document.createElement("style");
  st.textContent = ".cbtn{background:var(--card);color:var(--txt);border:1px solid var(--gold);border-radius:99px;padding:9px 18px;font:600 14px Inter,system-ui,sans-serif;cursor:pointer;text-decoration:none}.cbtn:hover{background:var(--gold);color:#1a1205}.cardbtn{margin-top:12px}";
  document.head.appendChild(st);

  function loadImg(src){
    return new Promise(function(res){
      if(!src) return res(null);
      var i = new Image(); i.crossOrigin = "anonymous";
      i.onload = function(){res(i)}; i.onerror = function(){res(null)};
      i.src = src;
    });
  }
  function firstImg(list){
    return list.reduce(function(p,u){return p.then(function(f){return f || loadImg(u)})}, Promise.resolve(null));
  }
  function rr(c,x,y,w,h,r){c.beginPath();c.moveTo(x+r,y);c.arcTo(x+w,y,x+w,y+h,r);c.arcTo(x+w,y+h,x,y+h,r);c.arcTo(x,y+h,x,y,r);c.arcTo(x,y,x+w,y,r);c.closePath()}
  function fit(c,text,maxW,size,weight,fam){
    do{ c.font = weight+" "+size+"px "+fam; size -= 2; }while(c.measureText(text).width > maxW && size > 14);
  }
  function champIcon(name){
    if(!DD.map) return null;
    var id = DD.map[norm(name)];
    return id ? "https://ddragon.leagueoflegends.com/cdn/"+DD.ver+"/img/champion/"+id+".png" : null;
  }

  window.buildCard = function(riot){
    var p = PLAYERS.filter(function(x){return x.riot === riot})[0]; if(!p) return Promise.reject();
    var st = STATS && STATS.players && STATS.players[riot];
    var rank = PLAYERS.slice().sort(function(a,b){return score(b)-score(a)}).map(function(x){return x.riot}).indexOf(riot) + 1;
    var hi = TIERS.indexOf(p.tier) >= 7, tcol = COL[p.tier] || "#f5c542";
    var top = st && st.champs && st.champs[0];
    return Promise.all([
      loadImg(p.avatar),
      p.unranked ? null : firstImg(embUrls(p.tier)),
      top ? loadImg(champIcon(top.champ)) : null
    ]).then(function(im){
      var cv = document.createElement("canvas"); cv.width = W; cv.height = H;
      var c = cv.getContext("2d"), SERIF = "Georgia,'Times New Roman',serif", SANS = "Inter,system-ui,Arial,sans-serif";
      // fond bordeaux + cadre doré
      var g = c.createLinearGradient(0,0,W,H); g.addColorStop(0,"#4a0f1f"); g.addColorStop(.55,"#7a2037"); g.addColorStop(1,"#3d0b19");
      rr(c,0,0,W,H,36); c.fillStyle = g; c.fill();
      c.save(); rr(c,0,0,W,H,36); c.clip(); c.strokeStyle = "rgba(255,255,255,.04)"; c.lineWidth = 2;
      for(var k=-H;k<W;k+=16){c.beginPath();c.moveTo(k,H);c.lineTo(k+H,0);c.stroke()} c.restore();
      var gg = c.createLinearGradient(0,0,W,H); gg.addColorStop(0,"#f3d98b"); gg.addColorStop(.5,"#b8892b"); gg.addColorStop(1,"#f3d98b");
      rr(c,14,14,W-28,H-28,28); c.strokeStyle = gg; c.lineWidth = 6; c.stroke();
      rr(c,30,30,W-60,H-60,20); c.strokeStyle = "rgba(243,217,139,.35)"; c.lineWidth = 2; c.stroke();
      // en-tête
      c.textAlign = "center"; c.fillStyle = "#f3d98b"; c.font = "700 24px "+SANS;
      c.fillText("♛  SOLOQ CHALLENGE  ♛", W/2, 84);
      // portrait
      var cx = W/2, cy = 300, R = 150;
      c.beginPath(); c.arc(cx,cy,R+14,0,7); c.fillStyle = gg; c.fill();
      c.beginPath(); c.arc(cx,cy,R+4,0,7); c.fillStyle = "#3d0b19"; c.fill();
      c.save(); c.beginPath(); c.arc(cx,cy,R,0,7); c.clip();
      if(im[0]){ var s = Math.max(2*R/im[0].width, 2*R/im[0].height), w = im[0].width*s, h = im[0].height*s; c.drawImage(im[0], cx-w/2, cy-h/2, w, h); }
      else { c.fillStyle = "hsl("+hue(p.name)+",55%,38%)"; c.fillRect(cx-R,cy-R,2*R,2*R); c.fillStyle = "#fff"; c.font = "800 150px "+SANS; c.textBaseline = "middle"; c.fillText(String(p.name).slice(0,1).toUpperCase(), cx, cy+6); c.textBaseline = "alphabetic"; }
      c.restore();
      // numéro de classement
      c.beginPath(); c.arc(cx+R-20, cy-R+30, 38, 0, 7); c.fillStyle = rank===1?"#e6b84a":rank===2?"#b8b8c4":rank===3?"#b9794a":"#f6ece0"; c.fill();
      c.lineWidth = 4; c.strokeStyle = "#3d0b19"; c.stroke();
      c.fillStyle = "#3d0b19"; c.font = "800 38px "+SERIF; c.fillText("#"+rank, cx+R-20, cy-R+43);
      // nom
      c.fillStyle = "#fff"; fit(c, p.name, W-120, 66, "800", SERIF); c.fillText(p.name, W/2, 546);
      c.fillStyle = "#e9cfd4"; c.font = "500 22px "+SANS; c.fillText(p.riot, W/2, 582);
      // rang
      var by = 618, bh = 150;
      rr(c,70,by,W-140,bh,22); c.fillStyle = "rgba(0,0,0,.28)"; c.fill(); c.strokeStyle = "rgba(243,217,139,.5)"; c.lineWidth = 2; c.stroke();
      var ex = 150, ey = by+bh/2;
      if(im[1]){ c.drawImage(im[1], ex-58, ey-58, 116, 116); }
      else { c.beginPath(); c.arc(ex,ey,48,0,7); c.fillStyle = p.unranked ? "#475569" : tcol; c.fill(); c.fillStyle = "#0b1220"; c.font = "800 40px "+SANS; c.fillText(p.unranked ? "?" : p.tier.slice(0,1), ex, ey+14); }
      c.textAlign = "left"; c.fillStyle = tcol;
      var rt = p.unranked ? "Non classé" : LBL[p.tier] + (hi ? "" : " " + ROM[p.div]);
      c.fillStyle = p.unranked ? "#e9cfd4" : "#fff"; c.font = "800 54px "+SERIF; c.fillText(rt, 240, ey+4);
      c.fillStyle = "#f3d98b"; c.font = "600 28px "+SANS; c.fillText(p.unranked ? "—" : p.lp + " LP", 240, ey+44);
      // champion principal
      var cy2 = 800;
      if(top){
        var ix = 90;
        rr(c,ix,cy2,100,100,16); c.save(); c.clip();
        if(im[2]) c.drawImage(im[2], ix, cy2, 100, 100); else { c.fillStyle = "#3d0b19"; c.fillRect(ix,cy2,100,100); }
        c.restore(); rr(c,ix,cy2,100,100,16); c.strokeStyle = gg; c.lineWidth = 4; c.stroke();
        c.fillStyle = "#e9cfd4"; c.font = "600 20px "+SANS; c.fillText("CHAMPION PRINCIPAL", ix+124, cy2+32);
        c.fillStyle = "#fff"; c.font = "800 36px "+SERIF; c.fillText(top.champ, ix+124, cy2+72);
        c.fillStyle = "#f3d98b"; c.font = "600 22px "+SANS; c.fillText(top.games+" parties · "+Math.round(100*top.wins/top.games)+"% de victoires", ix+124, cy2+100);
      } else {
        c.fillStyle = "#e9cfd4"; c.font = "italic 24px "+SERIF; c.fillText("Pas encore de parties pendant le challenge", 90, cy2+56);
      }
      // stats
      var wr = p.w+p.l ? Math.round(100*p.w/(p.w+p.l)) : 0;
      var cells = [["WINRATE", wr+"%"], ["PARTIES", String(p.w+p.l)], ["KDA", st ? Number(st.kda).toFixed(2) : "—"],
                   ["MEILLEURE SÉRIE", st ? st.best_win_streak+" V" : "—"]];
      var gx = 70, gw = (W-140-3*14)/4;
      cells.forEach(function(x,i){
        var bx = gx + i*(gw+14), byy = 940;
        rr(c,bx,byy,gw,110,16); c.fillStyle = "rgba(0,0,0,.28)"; c.fill(); c.strokeStyle = "rgba(243,217,139,.35)"; c.lineWidth = 2; c.stroke();
        c.textAlign = "center"; c.fillStyle = "#fff"; fit(c, x[1], gw-16, 42, "800", SANS); c.fillText(x[1], bx+gw/2, byy+58);
        c.fillStyle = "#e9cfd4"; c.font = "600 14px "+SANS; c.fillText(x[0], bx+gw/2, byy+90);
      });
      c.textAlign = "center"; c.fillStyle = "rgba(243,217,139,.8)"; c.font = "500 18px "+SANS;
      c.fillText("Challenge du "+fmt(START)+" au "+fmt(END)+" · EUW", W/2, 1086);
      return cv;
    });
  };

  var ov = null;
  function overlay(){
    if(ov) return ov;
    ov = document.createElement("div"); ov.className = "modal"; ov.hidden = true; ov.style.zIndex = 60;
    ov.innerHTML = '<div class="dlg" role="dialog" aria-modal="true" aria-label="Carte joueur" style="width:min(460px,100%);text-align:center">'
      + '<img id="cardimg" alt="Carte joueur" style="width:100%;border-radius:14px;display:block">'
      + '<div style="display:flex;gap:10px;margin-top:14px;flex-wrap:wrap;justify-content:center">'
      + '<a id="cdl" class="cbtn" download="carte.png">⬇ Télécharger</a><button id="csh" class="cbtn" type="button">📤 Partager</button><button id="ccl" class="cbtn" type="button">Fermer</button></div></div>';
    document.body.appendChild(ov);
    function close(){ov.hidden = true}
    ov.querySelector("#ccl").addEventListener("click", close);
    ov.addEventListener("click", function(e){ if(e.target === ov) close(); });
    document.addEventListener("keydown", function(e){ if(e.key === "Escape" && !ov.hidden){ e.stopImmediatePropagation(); close(); } }, true);
    return ov;
  }
  window.showCard = function(riot){
    var o = overlay(), img = o.querySelector("#cardimg"), dl = o.querySelector("#cdl"), sh = o.querySelector("#csh");
    img.removeAttribute("src"); o.hidden = false;
    buildCard(riot).then(function(cv){
      cv.toBlob(function(b){
        var url = URL.createObjectURL(b), nm = (PLAYERS.filter(function(x){return x.riot===riot})[0]||{}).name || "joueur";
        img.src = url; dl.href = url; dl.download = "carte-" + String(nm).toLowerCase().replace(/[^a-z0-9]+/g,"-") + ".png";
        var file = new File([b], dl.download, {type:"image/png"});
        sh.hidden = !(navigator.canShare && navigator.canShare({files:[file]}));
        sh.onclick = function(){ navigator.share({files:[file], title:"SoloQ Challenge"}).catch(function(){}); };
      }, "image/png");
    }).catch(function(){ o.hidden = true; });
  };
})();
