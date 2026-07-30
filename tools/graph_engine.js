// --- rules plane: generic presentation vocab for the rule dependency graph (M.rule_graph). Colours
// reference the template's theme CSS vars, so no source values live here and both themes just work. ---
var RULE_NODE_COLOR={governance:"var(--faint)",slot:"var(--cls-reference)",query_rule:"var(--cls-entity)",contract_rule:"var(--commit)",derivation:"var(--cls-measure)",concept:"var(--cls-grouping)",view:"var(--muted)",dq:"var(--cls-enumeration)"};
var RULE_SPECIES=[["governance","governance","var(--faint)"],["slot","decision slot","var(--cls-reference)"],["query_rule","query rule","var(--cls-entity)"],["contract_rule","concept rule","var(--commit)"],["derivation","derivation","var(--cls-measure)"],["concept","concept","var(--cls-grouping)"],["view","serving view","var(--muted)"],["dq","DQ finding","var(--cls-enumeration)"]];
var RULE_EDGE={locks:["var(--border)",1,"3 4"],governed_by:["var(--cls-reference)",1.7,""],applies_to:["var(--cls-entity)",1.5,""],on_concept:["var(--faint)",1.1,"1 4"],derives:["var(--cls-measure)",1.7,""],over:["var(--cls-measure)",1.2,"4 3"],validated_against:["var(--muted)",1.4,""],cross_reference:["var(--cls-enumeration)",1.2,"2 3"]};
var RULE_EDGE_LABEL={locks:"locks",governed_by:"governed by",applies_to:"applies to",on_concept:"on concept",derives:"derives",over:"operates over",validated_against:"validated",cross_reference:"evidence"};
function buildGraphData(mode){
  if(mode==="rules"){                                          // the RULE dependency plane — a pure map of M.rule_graph
    var rg=(M&&M.rule_graph)||{nodes:[],links:[]};
    var rn=(rg.nodes||[]).map(function(n){
      // klass drives the facet-category key; prefix "rk_" so a rules-plane species (e.g. "view") never
      // collides with a data-plane REL_GROUP of the same name on the session-shared graphHideCat.
      return {id:n.id,label:n.label,klass:"rk_"+n.kind,kind:"concept",color:RULE_NODE_COLOR[n.kind]||"var(--muted)",
              rules:0,href:"#graph",rgkind:n.kind,rkind:n.rkind||"",severity:n.severity||"",policy:n.policy||"",detail:n.detail||"",rank:n.rank};
    });
    var rl=(rg.links||[]).map(function(l){return {source:l.source,target:l.target,kind:l.kind,label:""};});
    return {nodes:rn, links:rl};
  }
  if(mode==="ontology"){
    return {nodes:M.graph.nodes.map(function(n){return {id:n.id,label:n.label,klass:n.klass,kind:"concept",rules:n.rules||0,href:"#c/"+encodeURIComponent(n.id)};}),
            links:M.graph.links.slice()};
  }
  var rels=M.relations||[];
  var relNodes=rels.map(function(r){return {id:"r:"+r.leaf,label:r.name,kind:"relation",group:r.group,rules:(r.bound_concepts||[]).length,href:"#r/"+encodeURIComponent(r.leaf),cols:r.columns||[]};});
  var relIds={}; relNodes.forEach(function(n){relIds[n.id]=1;});
  var fkLinks=[];
  rels.forEach(function(r){(r.foreign_keys||[]).forEach(function(fk){
    var t="r:"+fk.to_table; if(relIds[t]) fkLinks.push({source:"r:"+r.leaf,target:t,kind:"fk",label:fk.from_column,to_col:fk.to_column,card_from:"N",card_to:"1"});});});
  if(mode==="data"||mode==="er") return {nodes:relNodes, links:fkLinks};
  // both (Bindings) = the FULL union: concepts (bound and/or related) + relations, wired with
  // concept<->concept ontology relations (orel / hierarchy) + concept->relation binding edges + relation<->relation FK edges.
  var need={}, bind=[];
  rels.forEach(function(r){(r.bound_concepts||[]).forEach(function(b){
    need[b.id]=1; bind.push({source:"c:"+b.id,target:"r:"+r.leaf,kind:"binding",label:"reads"});});});
  var orel=[];
  (M.graph.links||[]).forEach(function(l){
    if(l.kind==="coground") return;                              // synthetic 'same serving table' edge — redundant once both concepts bind the same relation node
    need[l.source]=1; need[l.target]=1;
    orel.push({source:"c:"+l.source,target:"c:"+l.target,kind:(l.kind==="fk"?"orel":l.kind),label:l.label});
  });
  var conNodes=M.concepts.filter(function(c){return need[c.id];}).map(function(c){
    return {id:"c:"+c.id,label:c.label,klass:c.klass,kind:"concept",rules:c.rules.length,href:"#c/"+encodeURIComponent(c.id)};});
  return {nodes:conNodes.concat(relNodes), links:orel.concat(bind).concat(fkLinks)};
}
function graphNodeById(full,id){ for(var i=0;i<full.nodes.length;i++){ if(full.nodes[i].id===id) return full.nodes[i]; } return null; }
function graphNbrs(full,id){
  var out=[],seen={};
  full.links.forEach(function(l){ var o=l.source===id?l.target:(l.target===id?l.source:null);
    if(o&&!seen[o]){ seen[o]=1; var n=graphNodeById(full,o); if(n) out.push({node:n,kind:l.kind}); }});
  return out;
}
function graphSub(full,id,depth){
  var adj={}; full.links.forEach(function(l){(adj[l.source]=adj[l.source]||[]).push(l.target);(adj[l.target]=adj[l.target]||[]).push(l.source);});
  var keep={}; keep[id]=1; var fr=[id];
  for(var d=0;d<depth;d++){ var nx=[]; fr.forEach(function(x){(adj[x]||[]).forEach(function(y){if(!keep[y]){keep[y]=1;nx.push(y);}});}); fr=nx; }
  return {nodes:full.nodes.filter(function(n){return keep[n.id];}), links:full.links.filter(function(l){return keep[l.source]&&keep[l.target];})};
}
function focusNode(id){ if(graphFocus&&graphFocus!==id) focusHist.push(graphFocus); graphFocus=id; render(); }
var NBR_KIND={binding:"binds to (grounding)",orel:"relates to",fk:"joins (FK)",hierarchy:"rolls up",coground:"same serving table",dim:"related"};
function layoutFlow(nodes, links, er, dir){
  // Layered left→right layout: rank by directed edges (source left, target right), so every arrow flows rightward.
  var DIRK={fk:1,hierarchy:1,binding:1,orel:1,                  // which edge kinds carry flow direction
            governed_by:1,applies_to:1,on_concept:1,derives:1,over:1,validated_against:1,cross_reference:1};
  // `locks` (governance -> every rule) is deliberately EXCLUDED: it is a decorative spine, not a
  // dependency. Ranking it would collapse the whole rule set into one lane under the lock node.
  var out={}, inn={}, indeg={}, byId={}, seen={};
  nodes.forEach(function(n){ out[n.id]=[]; inn[n.id]=[]; indeg[n.id]=0; byId[n.id]=n; });
  links.forEach(function(l){
    if(!DIRK[l.kind] || l.s.id===l.t.id || !byId[l.s.id] || !byId[l.t.id]) return;
    var k=l.s.id+">"+l.t.id; if(seen[k]) return; seen[k]=1;
    out[l.s.id].push(l.t.id); inn[l.t.id].push(l.s.id); indeg[l.t.id]++;
  });
  var rank={};
  var preRanked = nodes.length && nodes.every(function(n){ return isFinite(n.rank); });
  if(preRanked){                                                // caller supplied fixed lanes (e.g. rule species)
    var used={}; nodes.forEach(function(n){ used[n.rank]=1; });
    var uniq=Object.keys(used).map(Number).sort(function(a,b){ return a-b; });
    var remap={}; uniq.forEach(function(r,i){ remap[r]=i; });   // compact away empty lanes (absent species)
    nodes.forEach(function(n){ rank[n.id]=remap[n.rank]; });    // barycenter (below) still orders within each lane
  } else {
    var ind={}, q=[], order=[];                                 // Kahn topological order (cycle-safe: remnants appended)
    nodes.forEach(function(n){ ind[n.id]=indeg[n.id]; if(!ind[n.id]) q.push(n.id); });
    while(q.length){ var u=q.shift(); order.push(u); out[u].forEach(function(v){ if(--ind[v]===0) q.push(v); }); }
    nodes.forEach(function(n){ if(order.indexOf(n.id)<0) order.push(n.id); });
    nodes.forEach(function(n){ rank[n.id]=0; });                // longest-path rank
    order.forEach(function(u){ out[u].forEach(function(v){ if(rank[u]+1>rank[v]) rank[v]=rank[u]+1; }); });
  }
  var maxr=0; nodes.forEach(function(n){ if(rank[n.id]>maxr) maxr=rank[n.id]; });
  var cols=[]; for(var r=0;r<=maxr;r++) cols[r]=[];
  nodes.forEach(function(n){ cols[rank[n.id]].push(n); });
  cols.forEach(function(col){ col.forEach(function(n,i){ n._fy=i; }); });     // seed order = input order
  function meanY(id){ var a=inn[id].concat(out[id]), s=0,c=0; a.forEach(function(x){ if(byId[x]&&isFinite(byId[x]._fy)){ s+=byId[x]._fy; c++; } }); return c?s/c:null; }
  for(var pass=0; pass<4; pass++){                              // barycenter sweeps to reduce edge crossings
    (pass%2===0?cols:cols.slice().reverse()).forEach(function(col){
      col.forEach(function(n){ var m=meanY(n.id); if(m!=null) n._fy=m; });
      col.sort(function(a,b){ return a._fy-b._fy; });
      col.forEach(function(n,i){ n._fy=i; });
    });
  }
  var tb=(dir==="tb");                                          // orientation: along = flow axis (rank), cross = within-rank
  function along(n){ return er?(tb?(n.bh||n.r*2):(n.bw||n.r*2)):n.r*2; }
  function across(n){ return er?(tb?(n.bw||n.r*2):(n.bh||n.r*2)):n.r*2; }
  var alongGap=er?90:64, cum=0, rankPos=[];                     // rank offset by cumulative node size along the flow axis
  for(var r2=0;r2<=maxr;r2++){ var mA=0; cols[r2].forEach(function(n){ var a=along(n); if(a>mA)mA=a; }); rankPos[r2]=cum+mA/2; cum+=mA+alongGap; }
  cols.forEach(function(col,r3){
    var mC=0; col.forEach(function(n){ var c=across(n); if(c>mC)mC=c; });
    var crossGap=(er?mC:0)+(er?24:44), tot=(col.length-1)*crossGap;
    col.forEach(function(n,i){ var a=rankPos[r3], c=i*crossGap-tot/2;
      if(tb){ n.x=c; n.y=a; } else { n.x=a; n.y=c; }
      n.vx=0; n.vy=0; n.fx=null; n.fy=null; });
  });
}
function viewGraph(){
  var modes=[["ontology","Ontology"],["data","Data plane"],["both","Bindings"],["er","ER"],["rules","Rules"]];
  var toggle='<div class="gmodes">'+modes.map(function(m){
    return '<a class="gmode'+(graphMode===m[0]?" active":"")+'" data-mode="'+m[0]+'" href="#graph">'+esc(m[1])+'</a>';}).join("")+'</div>';
  function eLeg(label,extra,kind){return '<div class="li'+(kind&&graphHideKinds[kind]?" off":"")+'"'+(kind?' data-edgekind="'+kind+'"':'')+'><svg width="24" height="8"><line x1="1" y1="4" x2="23" y2="4" '+extra+'/></svg>'+label+'</div>';}
  var clsLeg=CLASSES.map(function(k){return '<div class="li'+(graphHideCat[k]?" off":"")+'" data-nodecat="'+esc(k)+'">'+classDot(k)+CLASS_GLYPH[k]+' '+k+'</div>';}).join("");
  var relLeg=REL_GROUPS.map(function(g){return '<div class="li'+(graphHideCat[g]?" off":"")+'" data-nodecat="'+esc(g)+'"><span class="lane-dot" style="border-radius:2px;background:'+relColor(g)+'"></span>'+esc(g)+'</div>';}).join("");
  var sep='<span style="width:1px;background:var(--border);align-self:stretch"></span>', leg;
  if(graphMode==="ontology") leg=clsLeg+sep+eLeg("relation",'stroke="var(--muted)" stroke-width="1.8"',"fk")+eLeg("rolls up",'stroke="var(--accent)" stroke-width="1.8" stroke-dasharray="5 4"',"hierarchy")+eLeg("same table",'stroke="var(--border)" stroke-width="1.2"',"coground")+'<div class="li"><span class="gcard" style="position:static;stroke:none">0..N · 1</span> cardinality</div>';
  else if(graphMode==="data") leg=relLeg+sep+eLeg("joins (FK)",'stroke="var(--muted)" stroke-width="1.8"',"fk");
  else if(graphMode==="er") leg=relLeg+sep+'<div class="li'+(graphHideKinds["fk"]?" off":"")+'" data-edgekind="fk"><svg width="26" height="10"><line x1="2" y1="5" x2="24" y2="5" stroke="var(--muted)" stroke-width="1.4"/><path d="M22,5 L24,2 M22,5 L24,5 M22,5 L24,8" stroke="var(--muted)" fill="none" stroke-width="1.1"/><path d="M5,2 L5,8" stroke="var(--muted)" stroke-width="1.4"/></svg>FK · many → one</div>';
  else if(graphMode==="rules"){
    var _rg=buildGraphData("rules"), present={}, presentE={};        // legend only what's actually in THIS graph
    _rg.nodes.forEach(function(n){present[n.klass]=1;});             // n.klass is the "rk_"+kind facet key
    _rg.links.forEach(function(l){presentE[l.kind]=1;});
    var rspLeg=RULE_SPECIES.filter(function(s){return present["rk_"+s[0]];}).map(function(s){
      var cat="rk_"+s[0];
      return '<div class="li'+(graphHideCat[cat]?" off":"")+'" data-nodecat="'+esc(cat)+'"><span class="lane-dot" style="background:'+s[2]+'"></span>'+esc(s[1])+'</div>';}).join("");
    var reLeg=["governed_by","applies_to","on_concept","derives","over","validated_against","cross_reference","locks"].filter(function(k){return presentE[k];}).map(function(k){
      var re=RULE_EDGE[k]; return eLeg(RULE_EDGE_LABEL[k],'stroke="'+re[0]+'" stroke-width="'+Math.max(re[1],1.4)+'"'+(re[2]?' stroke-dasharray="'+re[2]+'"':''),k);}).join("");
    leg=rspLeg+sep+reLeg;
  }
  else leg=clsLeg+relLeg+sep+eLeg("relation",'stroke="var(--accent)" stroke-width="1.8"',"orel")+eLeg("rolls up",'stroke="var(--accent)" stroke-width="1.8" stroke-dasharray="5 4"',"hierarchy")+eLeg("binds",'stroke="var(--commit)" stroke-width="1.6" stroke-dasharray="2 4"',"binding")+eLeg("joins (FK)",'stroke="var(--muted)" stroke-width="1.8"',"fk");
  var full=buildGraphData(graphMode), focusHdr="", connects="";
  if(graphFocusOn && graphFocus){
    var fn=graphNodeById(full,graphFocus);
    if(fn){
      var nbrs=graphNbrs(full,graphFocus);
      focusHdr='<div class="focushdr"><span class="fh-label">◎ '+esc(fn.label)+'</span>'
        +'<a class="gbtn" href="'+esc(fn.href)+'">open ↗</a>'
        +'<span class="fh-depth">hops <a class="gchip'+(focusDepth===1?" on":"")+'" href="#graph" data-gfocus-depth="1">1</a>'
        +'<a class="gchip'+(focusDepth===2?" on":"")+'" href="#graph" data-gfocus-depth="2">2</a></span>'
        +(focusHist.length?'<a class="gbtn" href="#graph" data-gfocus-back="1">⤺ back</a>':'')
        +'<a class="gbtn" href="#graph" data-gfocus-clear="1">✕ show all</a>'
        +'<span class="fh-count">'+nbrs.length+' direct connection'+(nbrs.length!==1?"s":"")+'</span></div>';
      var byKind={}; nbrs.forEach(function(x){(byKind[x.kind]=byKind[x.kind]||[]).push(x.node);});
      var secs=Object.keys(byKind).map(function(k){
        var chips=byKind[k].map(function(n){
          return '<span class="nbr"><a class="nbr-focus" href="#graph" data-focus="'+esc(n.id)+'">'+(n.kind==="relation"?"▪ ":"● ")+esc(n.label)+'</a><a class="nbr-open" href="'+esc(n.href)+'" title="open its page">↗</a></span>';
        }).join("");
        return '<div><div class="nbr-k">'+esc(NBR_KIND[k]||k)+'</div><div class="nbr-row">'+chips+'</div></div>';
      }).join("");
      connects='<h2 class="sec">Connects to — '+nbrs.length+'</h2>'
        +'<div class="connects">'+(secs||'<p class="empty">Nothing connects to this object in this plane.</p>')+'</div>';
    } else { graphFocus=null; }
  }
  var ctl='<div class="graphctl">'
    +'<button class="gbtn'+(graphFocusOn?" on":"")+'" data-gfocus-toggle="1" type="button">◎ Focus'+(graphFocusOn?": on":"")+'</button>'
    +'<button class="gbtn" id="g-freeze" type="button">❄ Freeze</button>'
    +'<button class="gbtn" id="g-fit" type="button">⊡ Fit</button>'
    +(graphMode==="rules"?"":'<button class="gbtn'+(graphLayout==="flow"?" on":"")+'" data-layout="'+(graphLayout==="flow"?"force":"flow")+'" type="button">'+(graphLayout==="flow"?"✦ Force":"→ Flow")+'</button>')
    +'<button class="gbtn" id="g-reset" type="button">⤢ 1:1</button>'
    +(graphMode==="er"?'<button class="gbtn'+(erCompact?"":" on")+'" data-ercols="1" type="button">'+(erCompact?"⊞ Columns":"⊟ Compact")+'</button>':'')
    +(graphMode==="er"?'<button class="gbtn" data-erstraight="1" type="button" title="switch ER connectors">'+(erStraight?"⌐ Elbow":"╱ Straight")+'</button>':'')
    +(graphLayout==="flow"?'<button class="gbtn" data-flowdir="1" type="button" title="flow orientation">'+(flowDir==="tb"?"→ L-R":"↓ T-B")+'</button>':'')
    +'</div>';
  var clearChip=anyFilterOn()?'<div class="li" data-clearfilters="1" style="color:var(--accent);font-weight:650">✕ clear filters</div>':'';
  return '<div class="legend" style="margin:2px 0 10px;align-items:center">'+leg+clearChip+toggle+'</div>'
    +focusHdr
    +'<div class="graphwrap"><div class="graphhint">scroll = zoom · drag background = pan · drag node = move</div>'+ctl
    +'<svg id="gsvg"></svg></div>'
    +connects;
}
function initGraph(){
  var svg=document.getElementById("gsvg"); if(!svg) return;
  var NS="http://www.w3.org/2000/svg";
  var W=(svg.parentNode&&svg.parentNode.clientWidth)||880, H=(svg.clientHeight>200?svg.clientHeight:560);
  var vx=0, vy=0, vw=W, vh=H;                                  // view box (zoom + pan)
  function applyView(){ svg.setAttribute("viewBox", vx+" "+vy+" "+vw+" "+vh); }
  applyView();
  var er=(graphMode==="er");
  function C(tag){return document.createElementNS(NS,tag);}
  var G=(graphFocusOn && graphFocus) ? graphSub(buildGraphData(graphMode), graphFocus, focusDepth) : buildGraphData(graphMode);  var G=(graphFocusOn && graphFocus) ? graphSub(buildGraphData(graphMode), graphFocus, focusDepth) : buildGraphData(graphMode);
  (function(){                                                  // facet filters: drop hidden node-categories + hidden edge-kinds (and orphaned links)
    var kept={};
    G.nodes=G.nodes.filter(function(n){ var cat=(n.kind==="relation")?(n.group||""):(n.klass||""); if(graphHideCat[cat]) return false; kept[n.id]=1; return true; });
    G.links=G.links.filter(function(l){ return !graphHideKinds[l.kind] && kept[l.source] && kept[l.target]; });
  })();
  var nodes=G.nodes.map(function(n){return {id:n.id,label:n.label,klass:n.klass||"",kind:n.kind||"concept",group:n.group||"",href:n.href||("#c/"+encodeURIComponent(n.id)),rules:n.rules||0,cols:n.cols||[],color:n.color||"",rgkind:n.rgkind||"",detail:n.detail||"",rank:n.rank};});
  var idx={}; nodes.forEach(function(n){idx[n.id]=n;});
  var links=G.links.map(function(l){return {s:idx[l.source],t:idx[l.target],kind:l.kind,label:l.label||"",cf:l.card_from||"",ct:l.card_to||"",to:l.to_col||""};})
                   .filter(function(l){return l.s&&l.t;});
  var deg={}; links.forEach(function(l){deg[l.s.id]=(deg[l.s.id]||0)+1;deg[l.t.id]=(deg[l.t.id]||0)+1;});  var deg={}; links.forEach(function(l){deg[l.s.id]=(deg[l.s.id]||0)+1;deg[l.t.id]=(deg[l.t.id]||0)+1;});
  var R=Math.min(W,H)*0.34;
  nodes.forEach(function(n,i){var a=i/nodes.length*Math.PI*2; n.x=W/2+Math.cos(a)*R; n.y=H/2+Math.sin(a)*R; n.vx=0;n.vy=0;
    if(er && n.kind==="relation"){
      var cs=n.cols||[];
      if(erCompact){ n.shownCols=0; n.bw=Math.max(118,(n.label||"").length*7+18); n.bh=24; n.r=Math.max(n.bw,n.bh)*0.56; }
      else { var shown=Math.min(cs.length,18); n.shownCols=shown;
        var maxlen=(n.label||"").length; cs.slice(0,shown).forEach(function(c){var tl=(c.name||"").length+((c.role==="primary_key"||c.role==="foreign_key")?3:0); if(tl>maxlen)maxlen=tl;});
        n.bw=Math.max(132,maxlen*6.5+20); n.bh=20+shown*13.4+(cs.length>shown?13:0)+7; n.r=Math.max(n.bw,n.bh)*0.56; }
    } else if(n.kind==="relation"){ n.side=13+Math.min(7,n.rules); n.r=n.side*0.62; }
    else { n.r=8+Math.min(9,n.rules*0.7)+Math.min(4,deg[n.id]||0); }});
  var savedLayout=graphPos[graphMode], haveSaved=false;       // user-authored positions for THIS plane?
  if(savedLayout){ nodes.forEach(function(n){ var sp=savedLayout[n.id]; if(sp&&isFinite(sp.x)&&isFinite(sp.y)){ n.x=sp.x; n.y=sp.y; haveSaved=true; } }); }
  function snapPos(){ var pm=graphPos[graphMode]||(graphPos[graphMode]={}); nodes.forEach(function(m){ pm[m.id]={x:m.x,y:m.y}; }); savePrefs(); }  // MERGE — never drop other planes' / off-focus nodes

  while(svg.firstChild) svg.removeChild(svg.firstChild);
  var gL=C("g"), gLbl=C("g"), gN=C("g");
  svg.appendChild(gL); svg.appendChild(gLbl); svg.appendChild(gN);
  var showLabel=(graphMode==="ontology"||er), showCard=(graphMode==="ontology");
  links.forEach(function(l){
    var e=C(er?"path":"line"); e.setAttribute("class","glink "+l.kind); gL.appendChild(e); l.el=e;
    if(graphMode==="rules" && RULE_EDGE[l.kind]){ var _re=RULE_EDGE[l.kind]; e.setAttribute("stroke",_re[0]); e.setAttribute("stroke-width",_re[1]); if(_re[2]) e.setAttribute("stroke-dasharray",_re[2]); }  // rule edge-kinds have no .glink CSS — stroke inline (theme vars) so no template touch
    if(er && l.kind==="fk"){ l.footEl=C("path"); l.footEl.setAttribute("class","erm"); l.oneEl=C("path"); l.oneEl.setAttribute("class","erm"); gL.appendChild(l.footEl); gL.appendChild(l.oneEl); }
    if(!er && (l.kind==="fk"||l.kind==="hierarchy"||l.kind==="binding"||l.kind==="orel"||RULE_EDGE[l.kind])){ l.arrowEl=C("path"); l.arrowEl.setAttribute("class","garrow "+l.kind); if(graphMode==="rules" && RULE_EDGE[l.kind]) l.arrowEl.setAttribute("fill",RULE_EDGE[l.kind][0]); gL.appendChild(l.arrowEl); }  // directed: arrowhead at the 'to' end
    if((showLabel||l.kind==="orel"||l.kind==="hierarchy") && l.label && l.kind!=="coground"){ l.lblEl=C("text"); l.lblEl.setAttribute("class",er?"erkey":"glabel"); l.lblEl.textContent=trunc(l.label); gLbl.appendChild(l.lblEl); }
    if(showCard && l.cf){ l.cfEl=C("text"); l.cfEl.setAttribute("class","gcard"); l.cfEl.textContent=l.cf; gLbl.appendChild(l.cfEl); }
    if(showCard && l.ct){ l.ctEl=C("text"); l.ctEl.setAttribute("class","gcard"); l.ctEl.textContent=l.ct; gLbl.appendChild(l.ctEl); }
  });
  nodes.forEach(function(n){
    var g=C("g"); g.setAttribute("class","gnode "+(er&&n.kind==="relation"?("ernode "+slug(n.group)):(n.kind==="relation"?("rel "+slug(n.group)):n.klass))+(n.id===graphFocus?" focus":"")); n.g=g;
    if(er && n.kind==="relation"){
      var w=n.bw,h=n.bh,cs=n.cols||[],sh=n.shownCols||0,compact=erCompact;
      var box=C("rect"); box.setAttribute("class","erbox"); box.setAttribute("x",-w/2); box.setAttribute("y",-h/2); box.setAttribute("width",w); box.setAttribute("height",h); box.setAttribute("rx",5); g.appendChild(box);
      var hd=C("rect"); hd.setAttribute("class","erhead "+slug(n.group)); hd.setAttribute("x",-w/2); hd.setAttribute("y",-h/2); hd.setAttribute("width",w); hd.setAttribute("height",compact?h:20); hd.setAttribute("rx",5); g.appendChild(hd);
      var ht=C("text"); ht.setAttribute("class","erttl"); ht.setAttribute("text-anchor","middle"); ht.setAttribute("y",compact?4:-h/2+14); ht.textContent=trunc(n.label); g.appendChild(ht);
      if(!compact){
        n.colY={};
        cs.slice(0,sh).forEach(function(c,ci){
          var cy=-h/2+20+ci*13.4+11;
          var tx=C("text"); tx.setAttribute("class","ercol "+(c.role==="primary_key"?"pk":c.role==="foreign_key"?"fk":"")); tx.setAttribute("x",-w/2+8); tx.setAttribute("y",cy);
          tx.textContent=(c.name||"")+(c.role==="primary_key"?" PK":c.role==="foreign_key"?" FK":""); g.appendChild(tx);
          n.colY[c.name]=cy-3;   // FK connectors attach at this row (a hair above the baseline = glyph centre)
        });
        if(cs.length>sh){ var mt=C("text"); mt.setAttribute("class","ercol more"); mt.setAttribute("x",-w/2+8); mt.setAttribute("y",-h/2+20+sh*13.4+11); mt.textContent="+"+(cs.length-sh)+" more columns"; g.appendChild(mt); }
      }
    } else if(n.kind==="relation"){ var s=n.side, rc=C("rect");
      rc.setAttribute("x",-s/2); rc.setAttribute("y",-s/2); rc.setAttribute("width",s); rc.setAttribute("height",s); rc.setAttribute("rx",3); g.appendChild(rc);
    } else { var c=C("circle"); c.setAttribute("r",n.r); if(n.color) c.setAttribute("fill",n.color); g.appendChild(c); }
    var ti=C("title"); ti.textContent=n.label+(n.detail?"\n\n"+n.detail:""); g.appendChild(ti);
    if(!(er && n.kind==="relation")){ var t=C("text"); t.setAttribute("text-anchor","middle"); t.setAttribute("dy",-n.r-4); t.textContent=trunc(n.label); g.appendChild(t); }
    gN.appendChild(g);
    g.addEventListener("mouseenter",function(){hi(n);});
    g.addEventListener("mouseleave",function(){hi(null);});
    g.addEventListener("mousedown",function(ev){
      ev.preventDefault(); ev.stopPropagation(); var p=ptr(ev), ox=p.x-n.x, oy=p.y-n.y, moved=false;
      if(graphFrozen || er){                                   // frozen or ER: move ONLY this node, no re-layout
        function mmF(e2){var q=ptr(e2); n.x=q.x-ox; n.y=q.y-oy; moved=Math.abs(q.x-p.x)+Math.abs(q.y-p.y)>4; paint();}  // place freely, no canvas clamp
        function muF(){document.removeEventListener("mousemove",mmF);document.removeEventListener("mouseup",muF); if(!moved){ if(graphFocusOn) focusNode(n.id); else location.hash=n.href; } else snapPos(); }
        document.addEventListener("mousemove",mmF); document.addEventListener("mouseup",muF);
      } else {                                                 // live: pin + let physics settle around it
        n.fx=n.x; n.fy=n.y; alpha=Math.max(alpha,0.3); step();
        function mm(e2){var q=ptr(e2); n.fx=q.x-ox; n.fy=q.y-oy; moved=Math.abs(q.x-p.x)+Math.abs(q.y-p.y)>4; alpha=Math.max(alpha,0.25); step();}
        function mu(){document.removeEventListener("mousemove",mm);document.removeEventListener("mouseup",mu); if(!moved){ n.fx=null;n.fy=null; if(graphFocusOn) focusNode(n.id); else location.hash=n.href; } else { n.fx=n.x; n.fy=n.y; snapPos(); } }
        document.addEventListener("mousemove",mm); document.addEventListener("mouseup",mu);
      }
    });
  });
  function ptr(e){var b=svg.getBoundingClientRect(); return {x: vx+(e.clientX-b.left)/(b.width||1)*vw, y: vy+(e.clientY-b.top)/(b.height||1)*vh};}
  function hi(n){
    if(!n){nodes.forEach(function(m){m.g.classList.remove("dim","hot");}); links.forEach(function(l){l.el.classList.remove("dim");}); return;}
    var nb={}; nb[n.id]=1; links.forEach(function(l){if(l.s.id===n.id)nb[l.t.id]=1; if(l.t.id===n.id)nb[l.s.id]=1;});
    nodes.forEach(function(m){m.g.classList.toggle("dim",!nb[m.id]); m.g.classList.toggle("hot",m.id===n.id);});
    links.forEach(function(l){l.el.classList.toggle("dim",!(l.s.id===n.id||l.t.id===n.id));});
  }
  function boxEdge(n,tx,ty){ var dx=tx-n.x,dy=ty-n.y; if(!dx&&!dy) return {x:n.x,y:n.y};
    var hw=(n.bw||n.r*2)/2, hh=(n.bh||n.r*2)/2, s=Math.min(hw/(Math.abs(dx)||1e-6), hh/(Math.abs(dy)||1e-6));
    return {x:n.x+dx*s, y:n.y+dy*s}; }
  function paint(){
    links.forEach(function(l){
      if(er && l.kind==="fk"){                                 // orthogonal elbow, attach at FK / referenced column rows
        var ch=l.s, pa=l.t, side=(pa.x>=ch.x)?1:-1;             // child(l.s) holds the FK · parent(l.t) is referenced
        var chw=(ch.bw||ch.r*2)/2, paw=(pa.bw||pa.r*2)/2;
        var ay=ch.y+((ch.colY&&ch.colY[l.label]!=null)?ch.colY[l.label]:0);  // child FK-column row, else box centre
        var dy=pa.y+((pa.colY&&pa.colY[l.to]!=null)?pa.colY[l.to]:0);        // parent key-column row, else box centre
        var ax=ch.x+side*chw, dx=pa.x-side*paw;
        if(erStraight){                                        // straight diagonal connector, column-level attach
          l.el.setAttribute("d","M"+ax+","+ay+" L"+dx+","+dy);
          if(l.footEl){ var sux=dx-ax,suy=dy-ay,sud=Math.sqrt(sux*sux+suy*suy)||1; sux/=sud; suy/=sud; var spx=-suy,spy=sux,sapx=ax+sux*12,sapy=ay+suy*12;
            l.footEl.setAttribute("d","M"+sapx+","+sapy+" L"+ax+","+ay+" M"+sapx+","+sapy+" L"+(ax+spx*4)+","+(ay+spy*4)+" M"+sapx+","+sapy+" L"+(ax-spx*4)+","+(ay-spy*4));
            var sbx=dx-sux*8,sby=dy-suy*8; l.oneEl.setAttribute("d","M"+(sbx+spx*5)+","+(sby+spy*5)+" L"+(sbx-spx*5)+","+(sby-spy*5)); }
          if(l.lblEl){ l.lblEl.setAttribute("x",(ax+dx)/2); l.lblEl.setAttribute("y",(ay+dy)/2-2); }
          return;
        }
        var stub=14, midx=(ax+dx)/2;
        l.el.setAttribute("d","M"+ax+","+ay+" L"+(ax+side*stub)+","+ay+" L"+midx+","+ay+" L"+midx+","+dy+" L"+(dx-side*stub)+","+dy+" L"+dx+","+dy);
        if(l.footEl){                                           // crow's-foot (many) on the horizontal child stub
          var apx=ax+side*12;
          l.footEl.setAttribute("d","M"+apx+","+ay+" L"+ax+","+ay+" M"+apx+","+ay+" L"+ax+","+(ay+4)+" M"+apx+","+ay+" L"+ax+","+(ay-4));
          var bx=dx-side*8;                                     // one-bar on the horizontal parent stub
          l.oneEl.setAttribute("d","M"+bx+","+(dy+5)+" L"+bx+","+(dy-5));
        }
        if(l.lblEl){ l.lblEl.setAttribute("x",midx); l.lblEl.setAttribute("y",(ay+dy)/2-2); }
        return;
      }
      var x1,y1,x2,y2;
      if(er){ var p1=boxEdge(l.s,l.t.x,l.t.y), p2=boxEdge(l.t,l.s.x,l.s.y); x1=p1.x;y1=p1.y;x2=p2.x;y2=p2.y; }
      else { x1=l.s.x;y1=l.s.y;x2=l.t.x;y2=l.t.y; }
      l.el.setAttribute("x1",x1);l.el.setAttribute("y1",y1);l.el.setAttribute("x2",x2);l.el.setAttribute("y2",y2);
      if(l.arrowEl){ var ax=x2-x1,ay=y2-y1,adr=Math.sqrt(ax*ax+ay*ay)||1; ax/=adr; ay/=adr; var apx=-ay,apy=ax,tipd=(l.t.r||6)+2,aTx=x2-ax*tipd,aTy=y2-ay*tipd,aBx=aTx-ax*8,aBy=aTy-ay*8,asp=3.6;
        l.arrowEl.setAttribute("d","M"+aTx+","+aTy+" L"+(aBx+apx*asp)+","+(aBy+apy*asp)+" L"+(aBx-apx*asp)+","+(aBy-apy*asp)+" Z"); }
      if(l.lblEl){ l.lblEl.setAttribute("x",(x1+x2)/2); l.lblEl.setAttribute("y",(y1+y2)/2-2); }
      if(l.cfEl){ l.cfEl.setAttribute("x",x1+(x2-x1)*0.17); l.cfEl.setAttribute("y",y1+(y2-y1)*0.17-2); }
      if(l.ctEl){ l.ctEl.setAttribute("x",x1+(x2-x1)*0.83); l.ctEl.setAttribute("y",y1+(y2-y1)*0.83-2); }
    });
    nodes.forEach(function(n){n.g.setAttribute("transform","translate("+n.x+","+n.y+")");});
  }
  var alpha=1;
  function physics(){
    var i,j,a,b,dx,dy,d,d2,f,fx,fy, REP=er?(erCompact?40000:90000):2700, cen=er?0.0016:0.006, cap=er?60:24;
    for(i=0;i<nodes.length;i++){a=nodes[i];
      for(j=i+1;j<nodes.length;j++){b=nodes[j];
        dx=a.x-b.x; dy=a.y-b.y; d2=dx*dx+dy*dy+0.01; d=Math.sqrt(d2);
        f=REP/d2; fx=dx/d*f; fy=dy/d*f; a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;
        var minD=(a.r||10)+(b.r||10)+(er?18:12); if(d<minD){ var sep=(minD-d)*0.5; a.vx+=dx/d*sep;a.vy+=dy/d*sep; b.vx-=dx/d*sep;b.vy-=dy/d*sep; }  // hard min-separation: two nodes never overlap
      }}
    links.forEach(function(l){var L=er?(erCompact?180:340):(l.kind==="coground"?125:92); dx=l.t.x-l.s.x;dy=l.t.y-l.s.y;d=Math.sqrt(dx*dx+dy*dy)+0.01;
      f=(d-L)*0.03; fx=dx/d*f; fy=dy/d*f; l.s.vx+=fx;l.s.vy+=fy;l.t.vx-=fx;l.t.vy-=fy;});
    nodes.forEach(function(n){ n.vx+=(W/2-n.x)*cen; n.vy+=(H/2-n.y)*cen;
      if(n.fx!=null){n.x=n.fx;n.vx=0;} else {n.vx*=0.86; n.x+=Math.max(-cap,Math.min(cap,n.vx*alpha));}
      if(n.fy!=null){n.y=n.fy;n.vy=0;} else {n.vy*=0.86; n.y+=Math.max(-cap,Math.min(cap,n.vy*alpha));}
      if(!er){ n.x=Math.max(n.r+8,Math.min(W-n.r-8,n.x)); n.y=Math.max(n.r+18,Math.min(H-n.r-8,n.y)); }  // ER is unbounded — spread freely, Fit frames it
    });
  }
  function tick(){ physics(); paint(); alpha*=0.985; graphAnim = alpha>0.03 ? requestAnimationFrame(tick) : null; }
  function step(){ if(!graphFrozen && !er && !graphAnim) graphAnim=requestAnimationFrame(tick); }
  function fitView(){                                          // zoom/pan so every node is in frame
    if(!nodes.length) return;
    var minx=1e9,miny=1e9,maxx=-1e9,maxy=-1e9;
    nodes.forEach(function(n){ var hw=(n.bw||n.r*2)/2, hh=(n.bh||n.r*2)/2;
      minx=Math.min(minx,n.x-hw); maxx=Math.max(maxx,n.x+hw); miny=Math.min(miny,n.y-hh); maxy=Math.max(maxy,n.y+hh); });
    var pad=44, cw=(maxx-minx)+pad*2, ch=(maxy-miny)+pad*2, ar=W/H;
    if(cw/ch>ar) ch=cw/ar; else cw=ch*ar;
    cw=Math.max(cw,120); ch=Math.max(ch,120);
    vw=cw; vh=ch; vx=(minx+maxx)/2-cw/2; vy=(miny+maxy)/2-ch/2; applyView();
  }

  /* zoom (wheel, centered on cursor) + pan (drag the empty background) */
  svg.addEventListener("wheel",function(e){
    e.preventDefault(); var b=svg.getBoundingClientRect(), fxr=(e.clientX-b.left)/(b.width||1), fyr=(e.clientY-b.top)/(b.height||1);
    var mx=vx+fxr*vw, my=vy+fyr*vh, k=e.deltaY<0?0.85:1/0.85;
    var nvw=Math.min(W*8, Math.max(W*0.12, vw*k)), nvh=nvw*(H/W);
    vx=mx-fxr*nvw; vy=my-fyr*nvh; vw=nvw; vh=nvh; applyView();
  },{passive:false});
  svg.addEventListener("mousedown",function(e){
    if(e.target!==svg) return;                                 // only the empty background pans
    e.preventDefault(); var b=svg.getBoundingClientRect(), sx=e.clientX, sy=e.clientY, ovx=vx, ovy=vy;
    function mm(e2){ vx=ovx-(e2.clientX-sx)/(b.width||1)*vw; vy=ovy-(e2.clientY-sy)/(b.height||1)*vh; applyView(); }
    function mu(){ document.removeEventListener("mousemove",mm); document.removeEventListener("mouseup",mu); }
    document.addEventListener("mousemove",mm); document.addEventListener("mouseup",mu);
  });

  /* controls: Freeze (hold the layout, no auto-rearrange) + Reset view (zoom/pan) */
  var fb=document.getElementById("g-freeze");
  if(fb){ fb.textContent=graphFrozen?"▶ Physics":"❄ Freeze";
    fb.onclick=function(){ graphFrozen=!graphFrozen;
      if(graphFrozen){ if(graphAnim){cancelAnimationFrame(graphAnim);graphAnim=null;} }
      else { alpha=Math.max(alpha,0.5); step(); }
      fb.textContent=graphFrozen?"▶ Physics":"❄ Freeze"; }; }
  var rb=document.getElementById("g-reset");
  if(rb){ rb.onclick=function(){ vx=0;vy=0;vw=W;vh=H; applyView(); }; }
  var ftb=document.getElementById("g-fit");
  if(ftb){ ftb.onclick=function(){ fitView(); }; }

  if(!haveSaved && (graphLayout==="flow" || graphMode==="rules")){ layoutFlow(nodes, links, er, (graphMode==="rules"?"lr":flowDir)); paint(); fitView(); }   // rules plane always opens as fixed species lanes (left→right)
  else if(haveSaved){
    var unsaved=nodes.filter(function(n){ return !(savedLayout&&savedLayout[n.id]); });   // nodes added since the layout was saved (e.g. new registers) — settle just these into free space
    if(unsaved.length){ nodes.forEach(function(n){ if(savedLayout&&savedLayout[n.id]){ n.fx=n.x; n.fy=n.y; } }); for(var us=0;us<240;us++){ physics(); alpha*=0.985; } nodes.forEach(function(n){ n.fx=null; n.fy=null; }); alpha=0; }
    paint(); fitView();
  }                                                            // restored a hand-dragged layout: honour it, skip the settle
  else if(er){ for(var es=0;es<320;es++){ physics(); alpha*=0.985; } alpha=0; paint(); fitView(); }        // ER: settle statically, then frame it all
  else if(graphFrozen){ for(var stp=0;stp<300;stp++){ physics(); alpha*=0.985; } alpha=0; paint(); fitView(); }  // default: settle + auto-fit, no jitter
  else { step(); }

  graphSearchFn=function(q){                                  // wired to #search: grey non-matches, frame + pulse the hits
    q=(q||"").trim().toLowerCase();
    if(!q){ nodes.forEach(function(m){m.g.classList.remove("dim","hot","ghit");}); links.forEach(function(l){l.el.classList.remove("dim");}); return; }
    var hits=[];
    nodes.forEach(function(m){
      var hit=(m.label&&m.label.toLowerCase().indexOf(q)>=0)||(m.id&&m.id.toLowerCase().indexOf(q)>=0);
      m.g.classList.toggle("dim",!hit); m.g.classList.toggle("hot",hit); m.g.classList.toggle("ghit",hit); if(hit) hits.push(m);
    });
    links.forEach(function(l){ l.el.classList.toggle("dim",!(l.s.g.classList.contains("hot")||l.t.g.classList.contains("hot"))); });
    if(!hits.length) return;                                  // no match → leave the view where it is, just full-dim
    var minx=1e9,miny=1e9,maxx=-1e9,maxy=-1e9;                // frame the matched subset (fitView's math over hits only)
    hits.forEach(function(n){ var hw=(n.bw||n.r*2)/2, hh=(n.bh||n.r*2)/2; minx=Math.min(minx,n.x-hw); maxx=Math.max(maxx,n.x+hw); miny=Math.min(miny,n.y-hh); maxy=Math.max(maxy,n.y+hh); });
    var pad=90, cw=(maxx-minx)+pad*2, ch=(maxy-miny)+pad*2, ar=W/H;
    if(cw/ch>ar) ch=cw/ar; else cw=ch*ar;
    cw=Math.max(cw,220); ch=Math.max(ch,220);
    vw=cw; vh=ch; vx=(minx+maxx)/2-cw/2; vy=(miny+maxy)/2-ch/2; applyView();
  };
  if(state.q) graphSearchFn(state.q);                         // re-apply an active query after a re-init (mode / focus / ER-columns toggle)
}