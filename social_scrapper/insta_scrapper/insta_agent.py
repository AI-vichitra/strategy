import os
import sys
import asyncio
import random
import urllib.parse
from typing import Dict
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Load environment variables from .env file
load_dotenv()

INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

# The URL-encoded JavaScript bookmarklet provided by the user
BOOKMARKLET_ENCODED = """javascript:(function()%7B%0A      if(window.__IGRB__)return%3B%0A      window.__IGRB__%3Dtrue%3B%0A%0A      var stopped%3Dfalse%2C allPosts%3D%5B%5D%3B%0A%0A      var badge%3Ddocument.createElement('div')%3B%0A      Object.assign(badge.style%2C%7Bposition%3A'fixed'%2Cbottom%3A'22px'%2Cright%3A'22px'%2Cbackground%3A'%231a1a1a'%2CborderRadius%3A'8px'%2Cpadding%3A'12px 16px'%2CfontFamily%3A'monospace'%2CfontSize%3A'12px'%2CfontWeight%3A'500'%2Ccolor%3A'%23eee'%2CzIndex%3A'2147483647'%2CboxShadow%3A'0 4px 20px rgba(0%2C0%2C0%2C.3)'%2Cdisplay%3A'flex'%2CflexDirection%3A'column'%2Cgap%3A'6px'%2CminWidth%3A'220px'%7D)%3B%0A      var topRow%3Ddocument.createElement('div')%3B%0A      topRow.style.cssText%3D'display%3Aflex%3Balign-items%3Acenter%3Bjustify-content%3Aspace-between%3Bgap%3A12px%3B'%3B%0A      var titleEl%3Ddocument.createElement('div')%3B%0A      titleEl.style.cssText%3D'font-size%3A11px%3Bletter-spacing%3A1px%3Btext-transform%3Auppercase%3Bcolor%3A%23aaa%3B'%3B%0A      titleEl.textContent%3D'Instagram Report'%3B%0A      var stopBtn%3Ddocument.createElement('button')%3B%0A      stopBtn.textContent%3D'Stop'%3B%0A      stopBtn.style.cssText%3D'background%3A%23333%3Bborder%3A1px solid %23555%3Bborder-radius%3A4px%3Bcolor%3A%23f87171%3Bfont-size%3A10px%3Bfont-weight%3A600%3Bpadding%3A2px 8px%3Bcursor%3Apointer%3Bfont-family%3Amonospace%3B'%3B%0A      stopBtn.onclick%3Dfunction(e)%7Be.stopPropagation()%3Bstopped%3Dtrue%3BbuildReport()%3B%7D%3B%0A      topRow.appendChild(titleEl)%3BtopRow.appendChild(stopBtn)%3B%0A      var statusEl%3Ddocument.createElement('div')%3B%0A      statusEl.style.cssText%3D'color%3A%23ccc%3Bfont-size%3A12px%3B'%3B%0A      statusEl.textContent%3D'Starting...'%3B%0A      var bar%3Ddocument.createElement('div')%3B%0A      bar.style.cssText%3D'background%3A%23333%3Bborder-radius%3A999px%3Bheight%3A2px%3B'%3B%0A      var fill%3Ddocument.createElement('div')%3B%0A      fill.style.cssText%3D'background%3A%23eee%3Bheight%3A2px%3Bborder-radius%3A999px%3Bwidth%3A0%25%3Btransition%3Awidth .4s%3B'%3B%0A      bar.appendChild(fill)%3B%0A      badge.appendChild(topRow)%3Bbadge.appendChild(statusEl)%3Bbadge.appendChild(bar)%3B%0A      document.body.appendChild(badge)%3B%0A%0A      function setS(t)%7BstatusEl.textContent%3Dt%3B%7D%0A      function setP(p)%7Bfill.style.width%3DMath.min(100%2Cp)%2B'%25'%3B%7D%0A%0A      document.addEventListener('keydown'%2Cfunction onKey(e)%7B%0A        if(e.key%3D%3D%3D'Escape')%7Bdocument.removeEventListener('keydown'%2ConKey)%3Bstopped%3Dtrue%3BbuildReport()%3B%7D%0A      %7D)%3B%0A%0A      var username%3D(location.pathname.match(%2F%5E%5C%2F(%5B%5E%5C%2F%5D%2B)%5C%2F%3F%2F)%7C%7C%5B%5D)%5B1%5D%3B%0A      if(!username%7C%7C%5B'explore'%2C'reel'%2C'p'%2C'stories'%2C'direct'%2C'accounts'%5D.indexOf(username)>-1)%7B%0A        setS('Go to instagram.com%2Fusername first')%3Breturn%3B%0A      %7D%0A      setS('Looking up %40'%2Busername%2B'...')%3B%0A%0A      var appId%3D'936619743392459'%3B%0A      var headers%3D%7B'X-IG-App-ID'%3AappId%2C'X-Requested-With'%3A'XMLHttpRequest'%2C'Accept'%3A'application%2Fjson'%7D%3B%0A%0A      fetch('https%3A%2F%2Fwww.instagram.com%2Fapi%2Fv1%2Fusers%2Fweb_profile_info%2F%3Fusername%3D'%2BencodeURIComponent(username)%2C%7Bcredentials%3A'include'%2Cheaders%3Aheaders%7D)%0A        .then(function(r)%7Bif(!r.ok)%7Bthrow new Error('HTTP '%2Br.status)%3B%7Dreturn r.json()%3B%7D)%0A        .then(function(data)%7B%0A          var user%3Ddata%26%26data.data%26%26data.data.user%3B%0A          if(!user)%7Bthrow new Error('Could not read user data.')%3B%7D%0A          var postCount%3Duser.edge_owner_to_timeline_media%26%26user.edge_owner_to_timeline_media.count%7C%7C0%3B%0A          setS('%40'%2Busername%2B' · '%2BpostCount%2B' posts')%3B%0A          setP(10)%3B%0A          fetchPage(user.id%2Cnull%2C0%2CpostCount)%3B%0A        %7D)%0A        .catch(function()%7B%0A          setS('Trying fallback...')%3B%0A          fetch('https%3A%2F%2Fwww.instagram.com%2F'%2BencodeURIComponent(username)%2B'%2F'%2C%7Bcredentials%3A'include'%2Cheaders%3A%7B'Accept'%3A'text%2Fhtml'%7D%7D)%0A            .then(function(r)%7Breturn r.text()%3B%7D)%0A            .then(function(html)%7B%0A              var m%3Dhtml.match(%2F"owner"%3A%5C%7B"id"%3A"(%5Cd%2B)"%2F)%0A                %7C%7Chtml.match(%2F"user_id"%3A"(%5Cd%2B)"%2F)%0A                %7C%7Chtml.match(%2FprofilePage_(%5Cd%2B)%2F)%3B%0A              if(!m)%7Bthrow new Error('Could not find user ID')%3B%7D%0A              setS('Fetching posts...')%3BsetP(10)%3B%0A              fetchPage(m%5B1%5D%2Cnull%2C0%2C0)%3B%0A            %7D)%0A            .catch(function(err)%7BsetS('Error%3A '%2Berr.message)%3B%7D)%3B%0A        %7D)%3B%0A%0A      function fetchPage(userId%2CmaxId%2Cfetched%2Ctotal)%7B%0A        if(stopped)%7BbuildReport()%3Breturn%3B%7D%0A        var url%3D'https%3A%2F%2Fwww.instagram.com%2Fapi%2Fv1%2Ffeed%2Fuser%2F'%2BuserId%2B'%2F%3Fcount%3D12'%2B(maxId%3F'%26max_id%3D'%2BmaxId%3A'')%3B%0A        fetch(url%2C%7Bcredentials%3A'include'%2Cheaders%3Aheaders%7D)%0A          .then(function(r)%7Bif(!r.ok)%7Bthrow new Error('HTTP '%2Br.status)%3B%7Dreturn r.json()%3B%7D)%0A          .then(function(data)%7B%0A            var items%3Ddata.items%7C%7C%5B%5D%3B%0A            items.forEach(function(item)%7B%0A              if(stopped)return%3B%0A              var caption%3D''%2Chashtags%3D%5B%5D%3B%0A              if(item.caption%26%26item.caption.text)%7B%0A                caption%3Ditem.caption.text%3B%0A                hashtags%3Dcaption.match(%2F%23%5B%5Cw%5Cu0900-%5Cu097F%5Cu0600-%5Cu06FF%5Cu4e00-%5Cu9fff%5D%2B%2Fg)%7C%7C%5B%5D%3B%0A                var htStr%3Dhashtags.join(' ')%3B%0A                if(htStr)caption%3Dcaption.replace(htStr%2C'').trim()%3B%0A              %7D%0A              var thumb%3D''%3B%0A              if(item.image_versions2%26%26item.image_versions2.candidates%26%26item.image_versions2.candidates.length)%7B%0A                thumb%3Ditem.image_versions2.candidates%5B0%5D.url%3B%0A              %7D else if(item.carousel_media%26%26item.carousel_media%5B0%5D%26%26item.carousel_media%5B0%5D.image_versions2)%7B%0A                var c%3Ditem.carousel_media%5B0%5D.image_versions2.candidates%3B%0A                if(c%26%26c.length)thumb%3Dc%5B0%5D.url%3B%0A              %7D%0A              var date%3D''%3B%0A              if(item.taken_at)%7Btry%7Bdate%3Dnew Date(item.taken_at*1000).toLocaleDateString('en-US'%2C%7Byear%3A'numeric'%2Cmonth%3A'long'%2Cday%3A'numeric'%7D)%3B%7Dcatch(e)%7B%7D%7D%0A              allPosts.push(%7B%0A                thumb%3Athumb%2C%0A                href%3A'%2Fp%2F'%2B(item.code%7C%7Citem.shortcode%7C%7C'')%2C%0A                caption%3Acaption%2C%0A                hashtags%3Ahashtags%2C%0A                date%3Adate%2C%0A                likes%3Aitem.like_count!%3Dnull%3FString(item.like_count)%3A''%2C%0A                comments%3Aitem.comment_count!%3Dnull%3FString(item.comment_count)%3A''%0A              %7D)%3B%0A            %7D)%3B%0A            fetched%2B%3Ditems.length%3B%0A            var pct%3Dtotal>0%3FMath.min(95%2C10%2BMath.round((fetched%2Ftotal)*85))%3AMath.min(95%2C10%2Bfetched*2)%3B%0A            setP(pct)%3B%0A            setS(fetched%2B(total%3F' %2F '%2Btotal%3A'')%2B' posts fetched...')%3B%0A            var nextMaxId%3Ddata.next_max_id%3B%0A            if(nextMaxId%26%26!stopped%26%26items.length>0)%7B%0A              setTimeout(function()%7BfetchPage(userId%2CnextMaxId%2Cfetched%2Ctotal)%3B%7D%2C600)%3B%0A            %7D else %7B%0A              buildReport()%3B%0A            %7D%0A          %7D)%0A          .catch(function(err)%7B%0A            if(allPosts.length>0)%7BbuildReport()%3B%7D%0A            else%7BsetS('Error%3A '%2Berr.message)%3B%7D%0A          %7D)%3B%0A      %7D%0A%0A      function buildReport()%7B%0A        setP(100)%3B%0A        if(allPosts.length%3D%3D%3D0)%7BsetS('No posts fetched.'); window.save_html_report_to_python('<!-- NO POSTS FETCHED -->', username || 'unknown'); return;%7D%0A        setS('Converting images… ('%2BallPosts.length%2B' posts)')%3B%0A        stopBtn.style.display%3D'none'%3B%0A%0A        %2F%2F Convert all thumb URLs to base64 so images survive GoFullPage%0A        function imgToBase64(url)%7B%0A          return new Promise(function(resolve)%7B%0A            if(!url)%7Bresolve('')%3Breturn%3B%7D%0A            var img%3Dnew Image()%3B%0A            img.crossOrigin%3D'anonymous'%3B%0A            img.onload%3Dfunction()%7B%0A              try%7B%0A                var c%3Ddocument.createElement('canvas')%3B%0A                c.width%3Dimg.naturalWidth%3Bc.height%3Dimg.naturalHeight%3B%0A                var ctx%3Dc.getContext('2d')%3Bctx.drawImage(img%2C0%2C0)%3B%0A                resolve(c.toDataURL('image%2Fjpeg'%2C0.82))%3B%0A              %7Dcatch(e)%7Bresolve('')%3B%7D%0A            %7D%3B%0A            img.onerror%3Dfunction()%7Bresolve('')%3B%7D%3B%0A            %2F%2F Bust cache to help with CORS%0A            img.src%3Durl%2B(url.indexOf('%3F')>-1%3F'%26'%3A'%3F')%2B'_cb%3D'%2BDate.now()%3B%0A          %7D)%3B%0A        %7D%0A%0A        var total%3DallPosts.length%2C done%3D0%3B%0A        Promise.all(allPosts.map(function(p)%7B%0A          return imgToBase64(p.thumb).then(function(b64)%7B%0A            done%2B%2B%3B%0A            setS('Converting images '%2Bdone%2B'%2F'%2Btotal%2B'…')%3B%0A            setP(Math.round(done%2Ftotal*100))%3B%0A            p.b64%3Db64%3B%0A            return p%3B%0A          %7D)%3B%0A        %7D)).then(function(posts)%7B%0A          renderReport(posts)%3B%0A        %7D)%3B%0A      %7D%0A%0A      function renderReport(posts)%7B%0A        setS('Building report…')%3B%0A        var pname%3Dusername%7C%7C'instagram'%3B%0A        var date%3Dnew Date().toLocaleDateString('en-US'%2C%7Byear%3A'numeric'%2Cmonth%3A'long'%2Cday%3A'numeric'%7D)%3B%0A        function esc(s)%7Breturn String(s%7C%7C'').replace(%2F%26%2Fg%2C'%26amp%3B').replace(%2F<%2Fg%2C'%26lt%3B').replace(%2F>%2Fg%2C'%26gt%3B').replace(%2F"%2Fg%2C'%26quot%3B')%3B%7D%0A%0A        var cards%3Dposts.map(function(p)%7B%0A          %2F%2F Use base64 if available%2C fall back to URL%0A          var imgSrc%3Dp.b64%7C%7Cp.thumb%7C%7C''%3B%0A          var imgHtml%3DimgSrc%0A            %3F'<img src%3D"'%2Besc(imgSrc)%2B'" alt%3D""%2F>'%0A            %3A'<div class%3D"no-img">📷<%2Fdiv>'%3B%0A          var htHtml%3Dp.hashtags%26%26p.hashtags.length%0A            %3F'<div class%3D"ht">'%2Bp.hashtags.map(function(h)%7Breturn'<span>'%2Besc(h)%2B'<%2Fspan>'%3B%7D).join(' ')%2B'<%2Fdiv>'%0A            %3A''%3B%0A          var meta%3D%5B%0A            p.date%3Fesc(p.date)%3A''%2C%0A            p.likes%3F'♥ '%2BNumber(p.likes).toLocaleString()%3A''%2C%0A            p.comments%3F'💬 '%2BNumber(p.comments).toLocaleString()%3A''%0A          %5D.filter(Boolean).join(' · ')%3B%0A          return '<div class%3D"card">'%0A            %2B'<div class%3D"img-wrap">'%2BimgHtml%2B'<%2Fdiv>'%0A            %2B'<div class%3D"body">'%0A            %2B(meta%3F'<div class%3D"meta">'%2Bmeta%2B'<%2Fdiv>'%3A'')%0A            %2B'<div class%3D"cap">'%2Besc(p.caption)%2B'<%2Fdiv>'%0A            %2BhtHtml%0A            %2B(p.href%26%26p.href.length>3%3F'<a class%3D"link" href%3D"https%3A%2F%2Finstagram.com'%2Besc(p.href)%2B'" target%3D"_blank">view post<%2Fa>'%3A'')%0A            %2B'<%2Fdiv><%2Fdiv>'%3B%0A        %7D).join('')%3B%0A%0A        var html%3D'<!DOCTYPE html><html lang%3D"en"><head><meta charset%3D"UTF-8"%2F>'%0A          %2B'<title>%40'%2Besc(pname)%2B' report<%2Ftitle>'%0A          %2B'<link href%3D"https%3A%2F%2Ffonts.googleapis.com%2Fcss2%3Ffamily%3DIBM%2BPlex%2BMono%3Awght%40400%3B500%26family%3DIBM%2BPlex%2BSans%3Awght%40400%3B500%3B600%26display%3Dswap" rel%3D"stylesheet"%2F>'%0A          %2B'<style>*%7Bbox-sizing%3Aborder-box%3Bmargin%3A0%3Bpadding%3A0%3B%7Dbody%7Bbackground%3A%23f9f7f4%3Bfont-family%3A"IBM Plex Sans"%2Csans-serif%3Bpadding%3A40px 24px%3Bcolor%3A%231a1a1a%3B%7D.header%7Bmax-width%3A1100px%3Bmargin%3A0 auto 32px%3Bpadding-bottom%3A20px%3Bborder-bottom%3A2px solid %231a1a1a%3B%7D.header h1%7Bfont-size%3A20px%3Bfont-weight%3A600%3B%7D.header p%7Bfont-size%3A12px%3Bcolor%3A%23888%3Bfont-family%3A"IBM Plex Mono"%2Cmonospace%3Bmargin-top%3A4px%3B%7D.grid%7Bmax-width%3A1100px%3Bmargin%3A0 auto%3Bcolumns%3A2%3Bcolumn-gap%3A14px%3B%7D%40media(max-width%3A600px)%7B.grid%7Bcolumns%3A1%3B%7D%7D%40media print%7Bbody%7Bbackground%3A%23fff%3Bpadding%3A20px%3B%7D%7D.card%7Bbreak-inside%3Aavoid%3Bbackground%3A%23fff%3Bborder%3A1px solid %23e0e0e0%3Bborder-radius%3A6px%3Boverflow%3Ahidden%3Bmargin-bottom%3A14px%3B%7D.img-wrap img%7Bwidth%3A100%25%3Bdisplay%3Ablock%3Baspect-ratio%3A1%2F1%3Bobject-fit%3Acover%3B%7D.no-img%7Bwidth%3A100%25%3Baspect-ratio%3A1%2F1%3Bbackground%3A%23f0f0f0%3Bdisplay%3Aflex%3Balign-items%3Acenter%3Bjustify-content%3Acenter%3Bcolor%3A%23ccc%3Bfont-size%3A32px%3B%7D.body%7Bpadding%3A12px 14px%3B%7D.meta%7Bfont-size%3A11px%3Bcolor%3A%23999%3Bfont-family%3A"IBM Plex Mono"%2Cmonospace%3Bmargin-bottom%3A8px%3B%7D.cap%7Bfont-size%3A13px%3Bcolor%3A%23222%3Bline-height%3A1.65%3Bmargin-bottom%3A8px%3Bwhite-space%3Apre-wrap%3Bword-break%3Abreak-word%3B%7D.ht%7Bmargin-bottom%3A8px%3Bline-height%3A1.8%3B%7D.ht span%7Bcolor%3A%230095f6%3Bfont-size%3A12px%3Bmargin-right%3A4px%3Bfont-family%3A"IBM Plex Mono"%2Cmonospace%3B%7D.link%7Bfont-size%3A11px%3Bcolor%3A%23bbb%3Btext-decoration%3Anone%3Bfont-family%3A"IBM Plex Mono"%2Cmonospace%3B%7D.link%3Ahover%7Bcolor%3A%231a1a1a%3B%7D<%2Fstyle>'%0A          %2B'<%2Fhead><body>'%0A          %2B'<div class%3D"header"><h1>%40'%2Besc(pname)%2B'<%2Fh1><p>generated '%2Bdate%2B' · '%2Bposts.length%2B' posts<%2Fp><%2Fdiv>'%0A          %2B'<div class%3D"grid">'%2Bcards%2B'<%2Fdiv>'%0A          %2B'<%2Fbody><%2Fhtml>'%3B%0A%0A        %2F%2F Blob URL instead of about%3Ablank — GoFullPage can capture this%0A        var blob%3Dnew Blob(%5Bhtml%5D%2C%7Btype%3A'text%2Fhtml%3Bcharset%3Dutf-8'%7D)%3B%0A        var url%3DURL.createObjectURL(blob)%3B%0A        var tab%3Dwindow.open(url%2C'_blank')%3B%0A        if(!tab)%7B%0A          var a%3Ddocument.createElement('a')%3B%0A          a.href%3Durl%3B a.download%3D'%40'%2Bpname%2B'_report.html'%3B a.click()%3B%0A        %7D%0A%0A        setS('✅ Report ready! '%2Bposts.length%2B' posts')%3B%0A        setTimeout(function()%7B%0A          badge.style.opacity%3D'0'%3B%0A          setTimeout(function()%7Bbadge.remove()%3Bdelete window.__IGRB__%3B%7D%2C500)%3B%0A        %7D%2C5000)%3B%0A      %7D%0A%0A    %7D)()%3B"""

js_code = urllib.parse.unquote(BOOKMARKLET_ENCODED).replace("javascript:", "")

# Replace window.open with Python hook call
js_code = js_code.replace(
    "var tab=window.open(url,'_blank');",
    "window.save_html_report_to_python(html, pname);"
)

# Fix early return when 0 posts fetched
js_code = js_code.replace(
    "if(allPosts.length===0){setS('No posts fetched.');return;}",
    "if(allPosts.length===0){setS('No posts fetched.'); window.save_html_report_to_python('<!-- NO POSTS FETCHED -->', username || 'unknown'); return;}"
)

# Inject CSRF token to fix HTTP 401 Unauthorized errors
js_code = js_code.replace(
    "var headers={'X-IG-App-ID':appId,'X-Requested-With':'XMLHttpRequest','Accept':'application/json'};",
    "var csrf=(document.cookie.match(/csrftoken=([^;]+)/)||[])[1]; var headers={'X-IG-App-ID':appId,'X-Requested-With':'XMLHttpRequest','Accept':'application/json'}; if(csrf) headers['X-CSRFToken']=csrf;"
)

# Comment out fallback download
js_code = js_code.replace(
    "if(!tab){",
    "if(false){"
)

# Limit to 20 posts for efficiency
js_code = js_code.replace(
    "if(stopped){buildReport();return;}",
    "if(stopped || fetched >= 20){buildReport();return;}"
)

PROJECT_NAME = "default_brand"

# Dictionary of pending async events keyed by target name to support parallel workers
report_events: Dict[str, asyncio.Event] = {}

async def save_html_report_handler(html_content: str, pname: str):
    global PROJECT_NAME
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(os.path.dirname(script_dir))
    data_dir = os.path.join(base_dir, "docs", PROJECT_NAME)
    os.makedirs(data_dir, exist_ok=True)
    
    filename = f"{pname}_insta.html"
    filepath = os.path.join(data_dir, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"[SUCCESS] Generated Report for @{pname} -> {filepath}")
    
    # Notify the specific worker waiting for this pname report
    clean_pname = pname.strip(" ./@").lower()
    if clean_pname in report_events:
        report_events[clean_pname].set()
    else:
        # Fallback match if username canonicalized (e.g. zara. vs zara)
        for k, e in list(report_events.items()):
            if k.strip(" ./@") == clean_pname or k.startswith(clean_pname) or clean_pname.startswith(k):
                e.set()

async def human_delay(min_sec=1.5, max_sec=4.0):
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)

async def scrape_single_url(context, url: str, index: int, semaphore: asyncio.Semaphore):
    async with semaphore:
        # Stagger start time so parallel workers don't hit Instagram at the exact same millisecond
        await asyncio.sleep(index * random.uniform(1.2, 2.5))
        
        target_name = url.strip("/").split("/")[-1].strip(" ./@").lower()
        evt = asyncio.Event()
        report_events[target_name] = evt

        page = await context.new_page()
        print(f"\n[Worker {index+1}] Navigating to {url}...")
        
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_selector("header", timeout=20000)
            await human_delay(2.0, 4.5)
            
            # Simulate subtle human page interaction (scroll down a bit)
            await page.mouse.wheel(0, 300)
            await human_delay(1.0, 2.0)
            
            print(f"[Worker {index+1}] Injecting bookmarklet for @{target_name}...")
            await page.evaluate(js_code)
            
            # Wait for python hook or timeout after 90 seconds per profile
            await asyncio.wait_for(evt.wait(), timeout=90.0)
            print(f"[Worker {index+1}] Completed scraping for @{target_name}.")
            
        except asyncio.TimeoutError:
            print(f"[ERROR Worker {index+1}] Timed out waiting for report on @{target_name}")
        except Exception as e:
            print(f"[ERROR Worker {index+1}] Failed scraping {url}: {e}")
        finally:
            report_events.pop(target_name, None)
            await page.close()

async def run_report(urls):
    state_path = os.path.join(os.path.dirname(__file__), "insta_state.json")
    if not os.path.exists(state_path):
        print(f"\n[ERROR] Instagram login state file '{state_path}' not found!")
        print("To run the Instagram scraper silently in the background, please run:")
        print("  python social_scrapper/insta_scrapper/save_insta_state.py")
        return

    async with async_playwright() as p:
        # Launch Chromium with anti-bot detection evasion flags
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--ignore-certificate-errors",
                "--disable-extensions",
            ]
        )
        
        context = await browser.new_context(
            storage_state=state_path,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            }
        )
        
        # Mask navigator.webdriver fingerprint
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)
        
        # Expose python saving function
        await context.expose_function("save_html_report_to_python", save_html_report_handler)
        
        # Limit concurrency to max 3 parallel tabs to avoid IP rate-limiting
        semaphore = asyncio.Semaphore(3)
        print(f"Starting anti-detection Instagram scraper for {len(urls)} targets (parallel max=3)...")
        
        tasks = [
            scrape_single_url(context, url, idx, semaphore)
            for idx, url in enumerate(urls)
        ]
        
        await asyncio.gather(*tasks)
        print("\nAll Instagram URLs processed! Closing browser session...")
        await browser.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Parallel Anti-Detection Instagram Scraper")
    parser.add_argument("--project-name", default="default_brand", help="Name of the project")
    parser.add_argument("targets", nargs="+", help="Instagram usernames or URLs")
    args = parser.parse_args()
    
    PROJECT_NAME = args.project_name
    
    urls = []
    for target in args.targets:
        clean = target.strip()
        if clean.startswith("@"):
            clean = clean[1:]
        if not clean.startswith("http"):
            urls.append(f"https://www.instagram.com/{clean}/")
        else:
            urls.append(clean)
            
    asyncio.run(run_report(urls))
