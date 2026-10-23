/* Team sync for the public website. Marks, notes and added buildings are stored in
   Firebase Cloud Firestore under teams/<team code>/. The team code is long and random and
   only travels in the team link (…/#team=CODE), so people without it can't read or write.
   build/site.py fills in FIREBASE_CONFIG and copies this file to site/backend.js. */
(function () {
  'use strict';
  const FIREBASE_CONFIG = null; /* @config */
  const SDK = 'https://www.gstatic.com/firebasejs/10.14.1/';
  const TEAM_KEY = 'flyermap.v1.team', NAME_KEY = 'flyermap.v1.name';
  const get = k => { try { return localStorage.getItem(k) || ''; } catch { return ''; } };
  const put = (k, v) => { try { if (v) localStorage.setItem(k, v); else localStorage.removeItem(k); } catch {} };
  const validCode = c => /^[A-Za-z0-9_-]{20,64}$/.test(c || '');

  // Opening the team link stores the code on this phone, then tidies the address bar.
  const takeLink = () => {
    const m = /(?:^#|&)team=([A-Za-z0-9_-]{20,64})/.exec(location.hash);
    if (!m) return false;
    put(TEAM_KEY, m[1]);
    history.replaceState(null, '', location.pathname + location.search);
    return true;
  };
  takeLink();
  // the team link tapped while the site is already open only changes the #part, so reload then
  window.addEventListener('hashchange', () => { if (takeLink()) location.reload(); });

  const loadScript = src => new Promise((ok, fail) => {
    const s = document.createElement('script');
    s.src = src; s.onload = ok; s.onerror = () => fail(new Error('Could not load ' + src));
    document.head.appendChild(s);
  });
  const asErr = e => ({ code: (e && e.code) || 'unavailable', message: (e && e.message) || String(e) });

  // Same small surface the page uses from the Claude database: collection().limit().onSnapshot,
  // doc().onSnapshot / set / delete.
  function adapter(base) {
    const wrap = d => ({ id: d.id, exists: d.exists, data: () => d.data() });
    return {
      collection(name) {
        const limited = n => ({
          onSnapshot: (next, onErr) => base.collection(name).limit(n).onSnapshot(
            s => next({ docs: s.docs.map(wrap) }), e => onErr && onErr(asErr(e))),
        });
        return { limit: limited, onSnapshot: (next, onErr) => limited(1000).onSnapshot(next, onErr) };
      },
      doc(path) {
        const [c, id] = path.split('/');
        const ref = base.collection(c).doc(id);
        return {
          onSnapshot: (next, onErr) => ref.onSnapshot(d => next(wrap(d)), e => onErr && onErr(asErr(e))),
          set: data => ref.set(data).catch(e => { throw asErr(e); }),
          delete: () => ref.delete().catch(e => { throw asErr(e); }),
        };
      },
    };
  }

  // People are recorded by the name each staff member enters on their phone.
  const me = get(NAME_KEY).trim() || null;
  const user = {
    profiles: ids => Promise.resolve(Object.fromEntries([].concat(ids).filter(Boolean)
      .map(id => [id, { id, name: String(id), isMe: !!me && id === me }]))),
  };

  let wired = false;
  const TXT = {
    en: {
      team: 'Team code', teamPh: 'Paste the code from your manager', join: 'Join',
      bad: "That code doesn't look right. Copy the whole code or open the team link instead.",
      name: 'Your name', namePh: 'Shows on the deliveries you mark', save: 'Save', leave: 'Stop syncing this phone',
    },
    zh: {
      team: '团队代码', teamPh: '粘贴负责人发给你的代码', join: '加入',
      bad: '代码格式不对，请复制完整的代码，或直接打开团队链接。',
      name: '你的名字', namePh: '会显示在你标记的派发记录上', save: '保存', leave: '停止本机同步',
    },
  };
  let lang = 'en';
  const tx = k => (TXT[lang] || TXT.en)[k];
  window.FLYER_SITE = {
    modeText: {
      en: {
        pending: '',
        shared: 'This phone is synced with the team. Delivered marks, notes and added buildings update live for everyone, and saves made with no signal upload once you are back online.',
        readonly: 'The team database refused a change, so your marks are saved on this phone only for now.',
        local: FIREBASE_CONFIG
          ? 'Marks are saved on this phone only. To sync with the team, open the team link from your manager or enter the team code below.'
          : 'Marks are saved on this device only, so each phone keeps its own list.',
      },
      zh: {
        pending: '',
        shared: '本机已与团队同步。已派发标记、备注和添加的楼会实时更新给所有人；没有信号时保存的内容，会在恢复网络后自动上传。',
        readonly: '团队数据库拒绝了一次修改，所以你的标记暂时只保存在本机。',
        local: FIREBASE_CONFIG
          ? '标记只保存在本机。要与团队同步，请打开负责人发的团队链接，或在下面输入团队代码。'
          : '标记只保存在本设备上，每部手机各自记录。',
      },
    },

    async connect() {
      const team = get(TEAM_KEY);
      if (!FIREBASE_CONFIG || !validCode(team)) return null;
      await loadScript(SDK + 'firebase-app-compat.js');
      await loadScript(SDK + 'firebase-firestore-compat.js');
      const app = firebase.apps.length ? firebase.app() : firebase.initializeApp(FIREBASE_CONFIG);
      const fs = app.firestore();
      try { fs.settings({ ignoreUndefinedProperties: true, merge: true }); } catch {}
      try { await fs.enablePersistence({ synchronizeTabs: true }); } catch {}  // offline saves
      return { db: adapter(fs.collection('teams').doc(team)), user, meId: me };
    },

    render(el, mode, l) {
      lang = l === 'zh' ? 'zh' : 'en';
      if (!el || !FIREBASE_CONFIG || mode === 'pending') { if (el) el.innerHTML = ''; return; }
      if (mode === 'local') {
        el.innerHTML = `<div class="field"><label for="team-code">${tx('team')}</label>
          <div style="display:flex;gap:8px"><input id="team-code" autocomplete="off" spellcheck="false" placeholder="${tx('teamPh')}">
          <button class="btn" type="button" data-site="join">${tx('join')}</button></div>
          <span class="meta" id="team-msg"></span></div>`;
      } else {
        el.innerHTML = `<div class="field"><label for="me-name">${tx('name')}</label>
          <div style="display:flex;gap:8px"><input id="me-name" maxlength="40" autocomplete="nickname" placeholder="${tx('namePh')}">
          <button class="btn" type="button" data-site="name">${tx('save')}</button></div>
          <span class="meta"><button class="linkbtn" type="button" data-site="leave">${tx('leave')}</button></span></div>`;
        el.querySelector('#me-name').value = me || '';
      }
      if (wired) return;
      wired = true;
      el.addEventListener('click', e => {
        const b = e.target.closest('[data-site]'); if (!b) return;
        if (b.dataset.site === 'join') {
          const raw = (el.querySelector('#team-code').value || '').trim();
          const code = (/team=([A-Za-z0-9_-]+)/.exec(raw) || [, raw])[1];
          if (!validCode(code)) { el.querySelector('#team-msg').textContent = tx('bad'); return; }
          put(TEAM_KEY, code); location.reload();
        } else if (b.dataset.site === 'name') {
          put(NAME_KEY, (el.querySelector('#me-name').value || '').trim().slice(0, 40)); location.reload();
        } else if (b.dataset.site === 'leave') {
          put(TEAM_KEY, ''); location.reload();
        }
      });
    },
  };
})();
