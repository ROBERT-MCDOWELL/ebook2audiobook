()=>{
	try{
		let gr_root = (window.gradioApp && window.gradioApp()) || document;
		let gr_voice_player_hidden;
		let gr_audiobook_vtt;
		let gr_audiobook_sentence;
		let gr_audiobook_player;
		let gr_playback_time;
		let gr_progress;
		let gr_voice_play;
		let gr_ebook_textarea;
		let init_elements_timeout;
		let audio_filter = "none";
		// light/dark from the page as shown (body.dark): gradio's light/dark/system mode, or the mode the theme of the
		// theme dropdown forces. Chrome draws its audio controls light: inverted in dark. Firefox draws them dark:
		// inverted in light. The themes (html[data-e2a-mode]) give Chrome's controls their color-scheme and colors instead
		const get_audio_filter = ()=>{
			const is_dark = !!document.body?.classList.contains("dark");
			const native_dark = !!window.CSS?.supports?.("selector(::-moz-range-thumb)");
			const themed = !!document.documentElement.dataset.e2aMode;
			return (is_dark !== native_dark && (native_dark || !themed)) ? "invert(1) hue-rotate(180deg)" : "none";
		};
		const apply_audio_filter = ()=>{
			audio_filter = get_audio_filter();
			document.querySelectorAll("#gr_audiobook_player audio, #gr_audiobook_edit_player audio").forEach((player)=>{
				player.style.transition = "filter 1s ease";
				player.style.filter = audio_filter;
			});
		};
		// a theme picked or a light/dark change after the players are mounted
		if(!window._audio_filter_observer){
			window._audio_filter_observer = new MutationObserver(apply_audio_filter);
			window._audio_filter_observer.observe(document.body, {attributes: true, attributeFilter: ["class"]});
			window._audio_filter_observer.observe(document.documentElement, {attributes: true, attributeFilter: ["data-e2a-mode"]});
		}
		let tabs_open = false;
		let cues = [];
		let chapters = [];
		if(typeof window.onElementAvailable !== "function"){
			window.onElementAvailable = (selector, callback, { root = (window.gradioApp && window.gradioApp()) || document, once = false } = {})=> {
				const seen = new WeakSet();
				const fireFor = (context) => {
					context.querySelectorAll(selector).forEach((el) => {
						if (seen.has(el)) return;
						const success = callback(el);
						if (success !== false) {
							// Mark as seen only if callback succeeded
							seen.add(el);
							if (once) return;
						} else {
							// Retry check later (in case conditions weren’t met yet)
							setTimeout(() => fireFor(root), 300);
						}
					});
				};
				fireFor(root);
				const observer = new MutationObserver((mutations) => {
					for (const m of mutations) {
						for (const n of m.addedNodes) {
							if (n.nodeType !== 1) continue;
							if (n.matches?.(selector)) {
								if (!seen.has(n)) {
									const success = callback(n);
									if (success !== false) {
										seen.add(n);
										if (once) {
											observer.disconnect();
											return;
										}
									} else {
										setTimeout(() => fireFor(root), 300);
									}
								}
							} else {
								fireFor(n);
							}
						}
					}
				});
				observer.observe(root, { childList: true, subtree: true });
				return () => observer.disconnect();
			}
		}
		if(typeof window.init_interface !== "function"){
			window.init_interface = ()=>{
				try {
					gr_root = (window.gradioApp && window.gradioApp()) || document;
					gr_progress = (gr_root) ? gr_root.querySelector("#gr_progress") : undefined;
					if(!gr_root || !gr_progress){
						clearTimeout(init_elements_timeout);
						console.warn("Components not ready… retrying");
						init_elements_timeout = setTimeout(init_interface, 1000);
						return;
					}
					// Function to apply theme borders
					function applyThemeBorders(){
						const url = new URL(window.location);
						const theme = url.searchParams.get("__theme");
						let elColor = "#666666";
						if(theme == "dark"){
							elColor = "#fff";
						}else if(!theme){
							const osTheme = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
							if(osTheme){
								elColor = "#fff";
							}
						}
						gr_root.querySelectorAll("input[type='checkbox'], input[type='radio']")
							.forEach(cb => cb.style.border = "1px solid " + elColor);
					}
					// Run once on init
					applyThemeBorders();
					// Re-run when DOM changes (tabs, redraws, etc.)
					new MutationObserver(applyThemeBorders).observe(gr_root, {
						childList: true,
						subtree: true
					});
					// Keep your progress observer
					new MutationObserver(tab_progress).observe(gr_progress, {
						attributes: true,
						childList: true,
						subtree: true,
						characterData: true
					});
					if(!window._tab_progress_interval){
						window._tab_progress_interval = setInterval(tab_progress, 500);
					}
					window.gr_ebook_textarea_counter();
				}catch(e){
					console.warn("init_interface error:", e);
				}
			};
		}
		if(typeof(window._restoreSlider) !== "function"){
			window._restoreSlider = (slider, parseFn = parseFloat)=>{
				if(!slider) return;
				const container = slider.closest("div[id]");
				if(!container) return;
				const key = container.id.replace(/^gr_/, "");
				const saved = window.session_storage?.[key];
				if(saved === undefined || saved === null || saved === ""){
					return;
				}
				const parsed = parseFn(saved);
				if(!Number.isFinite(parsed)){
					return;
				}
				slider.value = parsed;
				slider.dispatchEvent(new Event("input", { bubbles: true }));
			};
		}
		if(typeof(window.init_xtts_sliders) !== "function"){
			window.init_xtts_sliders = ()=>{
				try{
					const q = (id) => gr_root.querySelector(`#gr_${id} input[type=number]`);
					window._restoreSlider(q("xtts_temperature"));
					window._restoreSlider(q("xtts_repetition_penalty"));
					window._restoreSlider(q("xtts_top_k"), (v) => parseInt(v, 10));
					window._restoreSlider(q("xtts_top_p"));
					window._restoreSlider(q("xtts_speed"));
				}catch(e){
					console.warn("init_xtts_sliders error:", e);
				}
			};
		}
		if(typeof(window.init_bark_sliders) !== "function"){
			window.init_bark_sliders = ()=>{
				try{
					const q = (id) => gr_root.querySelector(`#gr_${id} input[type=number]`);
					window._restoreSlider(q("bark_text_temp"));
					window._restoreSlider(q("bark_waveform_temp"));
				}catch(e){
					console.warn("init_bark_sliders error:", e);
				}
			};
		}
		if(typeof(window.init_zonos_sliders) !== "function"){
			window.init_zonos_sliders = ()=>{
				try{
					const q = (id) => gr_root.querySelector(`#gr_${id} input[type=number]`);
					window._restoreSlider(q("zonos_speaking_rate"));
					window._restoreSlider(q("zonos_emotion_happy"));
					window._restoreSlider(q("zonos_emotion_sad"));
					window._restoreSlider(q("zonos_emotion_angry"));
					window._restoreSlider(q("zonos_emotion_surprised"));
					window._restoreSlider(q("zonos_emotion_valence"));
					window._restoreSlider(q("zonos_emotion_arousal"));
					window._restoreSlider(q("zonos_emotion_strength"));
					window._restoreSlider(q("zonos_emotion_cfg_scale"));
				}catch(e){
					console.warn("init_zonos_sliders error:", e);
				}
			};
		}
		if(typeof(window.init_gptsovits_sliders) !== "function"){
			window.init_gptsovits_sliders = ()=>{
				try{
					const q = (id) => gr_root.querySelector(`#gr_${id} input[type=number]`);
					window._restoreSlider(q("gptsovits_speed"));
					window._restoreSlider(q("gptsovits_top_k"));
					window._restoreSlider(q("gptsovits_top_p"));
					window._restoreSlider(q("gptsovits_temperature"));
					window._restoreSlider(q("gptsovits_repetition_penalty"));
				}catch(e){
					console.warn("init_gptsovits_sliders error:", e);
				}
			};
		}
		if(typeof(window.init_orpheus_sliders) !== "function"){
			window.init_orpheus_sliders = ()=>{
				try{
					const q = (id) => gr_root.querySelector(`#gr_${id} input[type=number]`);
					window._restoreSlider(q("orpheus_temperature"));
					window._restoreSlider(q("orpheus_top_p"));
					window._restoreSlider(q("orpheus_repetition_penalty"));
				}catch(e){
					console.warn("init_orpheus_sliders error:", e);
				}
			};
		}
		if(typeof(window.init_sparktts_sliders) !== "function"){
			window.init_sparktts_sliders = ()=>{
				try{
					const q = (id) => gr_root.querySelector(`#gr_${id} input[type=number]`);
					window._restoreSlider(q("sparktts_temperature"));
					window._restoreSlider(q("sparktts_top_k"), (v) => parseInt(v, 10));
					window._restoreSlider(q("sparktts_top_p"));
				}catch(e){
					console.warn("init_sparktts_sliders error:", e);
				}
			};
		}
		if(typeof(window.init_chattts_sliders) !== "function"){
			window.init_chattts_sliders = ()=>{
				try{
					const q = (id) => gr_root.querySelector(`#gr_${id} input[type=number]`);
					window._restoreSlider(q("chattts_temperature"));
					window._restoreSlider(q("chattts_top_k"), (v) => parseInt(v, 10));
					window._restoreSlider(q("chattts_top_p"));
					window._restoreSlider(q("chattts_repetition_penalty"));
					window._restoreSlider(q("chattts_speed"), (v) => parseInt(v, 10));
				}catch(e){
					console.warn("init_chattts_sliders error:", e);
				}
			};
		}
		if(typeof(window.init_csm_sliders) !== "function"){
			window.init_csm_sliders = ()=>{
				try{
					const q = (id) => gr_root.querySelector(`#gr_${id} input[type=number]`);
					window._restoreSlider(q("csm_temperature"));
					window._restoreSlider(q("csm_top_k"), (v) => parseInt(v, 10));
				}catch(e){
					console.warn("init_csm_sliders error:", e);
				}
			};
		}
		if(typeof window.init_voice_player_hidden !== "function"){
			window.init_voice_player_hidden = ()=>{
				try{
					gr_voice_player_hidden = gr_root.querySelector("#gr_voice_player_hidden audio");
					gr_voice_play = gr_root.querySelector("#gr_voice_play");
					if(gr_voice_player_hidden && gr_voice_play){
						if(gr_voice_play.dataset.bound === "true") return;
						gr_voice_play.dataset.bound = "true";
						gr_voice_player_hidden.addEventListener("loadeddata", ()=>{
							gr_voice_play.textContent = "▶";
						});
						gr_voice_play.addEventListener("click", ()=>{
							if(gr_voice_player_hidden.paused){
								gr_voice_player_hidden.play().then(()=>{
									gr_voice_play.textContent = "⏸";
								}).catch(err => console.warn("Play failed:", err));
							}else{
								gr_voice_player_hidden.pause();
								gr_voice_play.textContent = "▶";
							}
						});
						gr_voice_player_hidden.addEventListener("pause", ()=>{
							gr_voice_play.textContent = "▶";
						});
						gr_voice_player_hidden.addEventListener("ended", ()=>{
							gr_voice_play.textContent = "▶";
						});
						gr_voice_player_hidden.addEventListener("play", ()=>{
							const v = window.session_storage?.playback_volume ?? 1;
							gr_voice_player_hidden.volume = v;
						});
						return true;
					}
				}catch(e){
					console.warn("init_voice_player_hidden error:", e);
				}
				return false;
			};
		}
		if(typeof(window.init_audiobook_player) !== "function"){
			window.init_audiobook_player = (el)=>{
				try{
					gr_root = (window.gradioApp && window.gradioApp()) || document;
					if(!gr_root){
						return false;
					}
					const player = (el && el.isConnected) ? el : gr_root.querySelector("#gr_audiobook_player audio");
					if(!player){
						return false;
					}
					gr_audiobook_player = player;
					if(player.dataset.bound === "true"){
						return true;
					}
					player.dataset.bound = "true";
					let lastCue = null;
					let fade_timeout = null;
					let raf_id = null;
					function q_sentence(){
						if(!gr_audiobook_sentence || !gr_audiobook_sentence.isConnected){
							gr_audiobook_sentence = gr_root.querySelector("#gr_audiobook_sentence textarea");
						}
						return gr_audiobook_sentence;
					}
					function q_playback_time(){
						if(!gr_playback_time || !gr_playback_time.isConnected){
							gr_playback_time = gr_root.querySelector("#gr_playback_time input, #gr_playback_time textarea");
						}
						return gr_playback_time;
					}
					function push_time(value){
						const el = q_playback_time();
						if(!el){
							return false;
						}
						el.value = String(value);
						el.dispatchEvent(new Event("input", {bubbles: true}));
						return true;
					}
					function safe_volume(value){
						const vol = parseFloat(value);
						return Number.isFinite(vol) ? Math.min(Math.max(vol, 0), 1) : 1;
					}
					function is_playing(){
						return !!(player.isConnected && !player.paused && !player.ended && player.readyState >= 2);
					}
					function start_playback(){
						if(raf_id === null && is_playing()){
							raf_id = requestAnimationFrame(trackPlayback);
						}
					}
					function stop_playback(){
						if(raf_id !== null){
							cancelAnimationFrame(raf_id);
							raf_id = null;
						}
					}
					function trackPlayback(){
						raf_id = null;
						try{
							window.session_storage.playback_time = parseFloat(player.currentTime);
							const sentence = q_sentence();
							const cue = findCue(window.session_storage.playback_time);
							if(sentence && !sentence.disabled && !sentence.readOnly){
								// sentence editor open: never overwrite the text being edited
								lastCue = null;
							}else if(sentence && cue && cue !== lastCue){
								if(fade_timeout){
									sentence.style.opacity = "1";
								}else{
									sentence.style.opacity = "0";
								}
								sentence.style.transition = "none";
								sentence.value = cue.text;
								sentence.classList.toggle("interlude-cue", cue.interlude !== null && cue.interlude !== undefined);
								show_cue_position(cue);
								clearTimeout(fade_timeout);
								fade_timeout = setTimeout(() => {
									const el = q_sentence();
									if(el){
										el.style.transition = "opacity 0.15s ease-in";
										el.style.opacity = "1";
									}
									fade_timeout = null;
								}, 33);
								lastCue = cue;
							}else if(!cue && lastCue !== null){
								lastCue = null;
							}
						}catch(e){
							console.warn("gr_audiobook_player tracking error:", e);
						}
						if(is_playing()){
							raf_id = requestAnimationFrame(trackPlayback);
						}
					}
					player.addEventListener("loadeddata", ()=>{
						player.style.transition = "filter 1s ease";
						player.style.filter = audio_filter;
						player.currentTime = parseFloat(window.session_storage?.playback_time) || 0;
						player.volume = safe_volume(window.session_storage?.playback_volume);
					});
					player.addEventListener("play", start_playback);
					player.addEventListener("playing", start_playback);
					player.addEventListener("waiting", stop_playback);
					player.addEventListener("pause", ()=>{
						stop_playback();
						push_time(player.currentTime);
					});
					player.addEventListener("seeked", ()=>{
						window.session_storage.playback_time = player.currentTime;
						stop_playback();
						trackPlayback();
					});
					player.addEventListener("ended", ()=>{
						stop_playback();
						const sentence = q_sentence();
						if(sentence && (sentence.disabled || sentence.readOnly)){
							sentence.value = "…";
						}
						window.session_storage.playback_time = 0;
						lastCue = null;
						push_time(0);
					});
					player.addEventListener("emptied", stop_playback);
					player.addEventListener("abort", stop_playback);
					player.addEventListener("error", stop_playback);
					player.addEventListener("volumechange", ()=>{
						window.session_storage.playback_volume = player.volume;
						gr_voice_player_hidden = gr_root.querySelector("#gr_voice_player_hidden audio");
						if(gr_voice_player_hidden){
							gr_voice_player_hidden.volume = player.volume;
							gr_voice_player_hidden.dispatchEvent(new Event("volumechange", { bubbles: true }));
						}
					});
					audio_filter = get_audio_filter();
					player.style.transition = "filter 1s ease";
					player.style.filter = audio_filter;
					player.volume = safe_volume(window.session_storage?.playback_volume);
					q_sentence();
					q_playback_time();
					start_playback();
					return true;
				}catch(e){
					console.warn("init_audiobook_player error:", e);
				}
				return false;
			};
		}
		if(typeof window.gr_ebook_textarea_counter !== "function"){
			window.gr_ebook_textarea_counter = function(){
				const container = document.querySelector("#gr_ebook_textarea");
				if(container){
					const textarea = container.querySelector("textarea");
					const max_ebook_textarea_length = textarea.maxLength;
					const ebook_textarea_toolbar = document.querySelector("#ebook_textarea_toolbar");
					document.querySelector("#ebook_textarea_toolbar")?.remove();
					container.style.position = "relative";
					const toolbar = document.createElement("div");
					toolbar.id = toolbar.name = "ebook_textarea_toolbar";
					toolbar.style.cssText = "position:absolute;top:4px;right:8px;display:flex;align-items:center;gap:6px;z-index:1;";
					const counter = document.createElement("span");
					counter.style.cssText = "font-size:0.85em;color:var(--body-text-color);";
					counter.textContent = textarea.value.length + " / " + max_ebook_textarea_length;
					toolbar.appendChild(counter);
					const btn = document.createElement("button");
					btn.textContent = "🗑";
					btn.id = btn.name = "clear_ebook_textarea";
					btn.className = "micro-btn";
					btn.addEventListener("click", ()=>{
						textarea.value = "";
						textarea.dispatchEvent(new Event("input", {bubbles: true}));
						counter.textContent = "0 / " + max_ebook_textarea_length;
						counter.style.color = "var(--body-text-color)";
					});
					textarea.addEventListener("input", ()=>{
						const len = textarea.value.length;
						counter.textContent = len + " / " + max_ebook_textarea_length;
						counter.style.color = len >= max_ebook_textarea_length ? "red" : "var(--body-text-color)";
					});
					toolbar.appendChild(btn);
					container.appendChild(toolbar);
				}
			};
		}
		if(typeof(window.tab_progress) !== "function"){
			window.tab_progress = ()=>{
				try{
					const gr_root = (window.gradioApp && window.gradioApp()) || document;
					const el = gr_root.querySelector("#gr_progress");
					const val = el?.value || el?.textContent || "";
					const valArray = splitAtLastDash(val);
					if(valArray[1]){
						const title = valArray[0].trim().split(/ (.*)/)[1].trim();
						const percentage = valArray[1].trim();
						const titleShort = title.length >= 20 ? title.slice(0, 20).trimEnd() + "…" : title;
						document.title = titleShort + ": " + percentage;
					}else{
						document.title = "Ebook2Audiobook";
					}
				}catch(e){
					console.warn("tab_progress error:", e);
				}
			};
		}
		if(typeof(window.splitAtLastDash) !== "function"){
			window.splitAtLastDash = function(s){
				const idx = s.lastIndexOf("-");
				if(idx === -1){
					return [s];
				}
				return [s.slice(0, idx).trim(), s.slice(idx + 1).trim()];
			};
		}
		if(typeof(window.load_vtt) !== "function"){
			window.load_vtt = ()=>{
				try{
					gr_audiobook_vtt = gr_root.querySelector("#gr_audiobook_vtt textarea");
					gr_audiobook_sentence = gr_root.querySelector("#gr_audiobook_sentence textarea");
					if(gr_audiobook_sentence){
						gr_audiobook_sentence.style.fontSize = "14px";
						gr_audiobook_sentence.style.fontWeight = "bold";
						gr_audiobook_sentence.style.width = "100%";
						gr_audiobook_sentence.style.height = "auto";
						gr_audiobook_sentence.style.textAlign = "center";
						gr_audiobook_sentence.style.margin = "0";
						gr_audiobook_sentence.style.padding = "7px 0 7px 0";
						gr_audiobook_sentence.style.lineHeight = "14px";
						const txt = gr_audiobook_vtt.value;
						if(txt == ""){
							gr_audiobook_sentence.value = "…";
						}else{
							parseVTT(txt);
						}
						show_cue_position(null);
					}
				}catch(e){
					console.warn("load_vtt error:", e);
				}
			};
		}
		if(typeof(window.parseVTT) !== "function"){
			 window.parseVTT = (vtt)=>{
				function pushCue(){
					if(start !== null && end !== null && textBuffer.length){
						// cue id "chapter <block index>": a marker written by build_vtt_file() at each block's first
						// sentence. Kept out of the sentence cues: they feed the clickable ticks under the player
						// (render_chapter_marks) instead of the sentence display
						const chapter = /^chapter (\d+)$/.exec(cueId);
						if(chapter){
							chapters.push({ start: start, block: parseInt(chapter[1], 10), title: textBuffer.join(" ").trim() });
						}else{
						// cue id "interlude <block index>" marks an interlude; sentence_idx counts sentence cues only
						const interlude = /^interlude \d+$/.test(cueId) ? parseInt(cueId.split(" ")[1], 10) : null;
						// cue id "block <block index> sentence <sentence index>": where the sentence is in e2a (no id in older audiobooks)
						const position = /^block (\d+) sentence (\d+)$/.exec(cueId);
						cues.push({ start, end, text: textBuffer.join("\n"), idx: cues.length, interlude: interlude, sentence_idx: interlude === null ? sentenceCount++ : -1,
							block: position ? parseInt(position[1], 10) : interlude, sentence: position ? parseInt(position[2], 10) : null });
						}
					}
					start = end = null;
					cueId = "";
					textBuffer.length = 0;
				}
				const lines = vtt.split(/\r?\n/);
				const timePattern = /(\d{2}:)?\d{2}:\d{2}\.\d{3}/;
				let start = null, end = null, cueId = "", sentenceCount = 0;
				cues = [];
				chapters = [];
				window.audiobook_chapters = chapters;
				const textBuffer = [];
				for(let i = 0, len = lines.length; i < len; i++){
					const line = lines[i];
					if(!line.trim()){ pushCue(); continue; }
					if(line.includes("-->")){
						const [s, e] = line.split("-->").map(l => l.trim().split(" ")[0]);
						if(timePattern.test(s) && timePattern.test(e)){
							start = toSeconds(s);
							end = toSeconds(e);
						}
					}else if(start === null){
						cueId = line.trim();
					}else if(!timePattern.test(line)){
						textBuffer.push(line);
					}
				}
				pushCue();
				window.render_chapter_marks();
			}
		}
		if(typeof(window.render_chapter_marks) !== "function"){
			// clickable ticks under #gr_audiobook_player, one per "chapter <n>" cue parsed above. Gradio's Audio renders
			// native controls that cannot be styled per-mark, so the ticks go on a thin overlay strip right below it;
			// hovering shows the chapter title, clicking jumps the audio there. No-op for older vtts without chapter cues
			window.render_chapter_marks = ()=>{
				try{
					const wrap = gr_root.querySelector("#gr_audiobook_player");
					if(!wrap){
						return;
					}
					const player = wrap.querySelector("audio");
					let strip = wrap.querySelector(".chapter-marks");
					if(!chapters.length){
						if(strip){
							strip.remove();
						}
						return;
					}
					if(!strip){
						strip = document.createElement("div");
						strip.className = "chapter-marks";
						strip.style.cssText = "position:relative;height:10px;margin:2px 4px 0 4px;user-select:none;";
						wrap.appendChild(strip);
					}else{
						strip.innerHTML = "";
					}
					const duration = player && Number.isFinite(player.duration) && player.duration > 0 ? player.duration : 0;
					if(duration <= 0){
						return;
					}
					for(const ch of chapters){
						const mark = document.createElement("div");
						mark.title = "Ch " + (ch.block + 1) + ": " + ch.title;
						mark.style.cssText = "position:absolute;top:1px;width:2px;height:8px;background:var(--body-text-color, #888);opacity:0.7;cursor:pointer;border-radius:1px;transform:translateX(-1px);";
						mark.style.left = Math.min(100, Math.max(0, (ch.start / duration) * 100)) + "%";
						mark.addEventListener("click", ()=>{
							const p = gr_root.querySelector("#gr_audiobook_player audio");
							if(p){
								p.currentTime = ch.start;
							}
						});
						strip.appendChild(mark);
					}
				}catch(e){
					console.warn("render_chapter_marks error:", e);
				}
			};
		}
		if(typeof(window.toSeconds) !== "function"){
			window.toSeconds = function(ts){
				const parts = ts.split(":");
				if(parts.length === 3){
					return parseInt(parts[0], 10) * 3600 +
						   parseInt(parts[1], 10) * 60 +
						   parseFloat(parts[2]);
				}
				return parseInt(parts[0], 10) * 60 + parseFloat(parts[1]);
			};
		}
		if(typeof(window.findCue) !== "function"){
			window.findCue = function(time){
				let lo = 0, hi = cues.length - 1;
				while(lo <= hi){
					const mid = (lo + hi) >> 1;
					const cue = cues[mid];
					if(time < cue.start){
						hi = mid - 1;
					}else if(time >= cue.end){
						lo = mid + 1;
					}else{
						return cue;
					}
				}
				return null;
			};
		}
		if(typeof(window.show_cue_position) !== "function"){
			// block and sentence of the cue playing, on one line under its text (♪ for an interlude, nothing without a cue
			// id). The words come from the hidden label of gr_audiobook_sentence: "block|sentence" in the UI language
			window.show_cue_position = function(cue){
				try{
					const sentence = gr_root.querySelector("#gr_audiobook_sentence textarea");
					if(!sentence || !sentence.parentElement){
						return;
					}
					let position = sentence.parentElement.querySelector(":scope > .cue-position");
					if(!position){
						position = document.createElement("div");
						position.className = "cue-position";
						sentence.after(position);
					}
					if(!cue || cue.block === null || cue.block === undefined){
						position.hidden = true;
						return;
					}
					const label = gr_root.querySelector('#gr_audiobook_sentence [data-testid="block-info"]');
					const [word_block, word_sentence] = ((label && label.textContent.includes("|")) ? label.textContent : "block|sentence").split("|");
					position.textContent = `${word_block} ${cue.block} · ` + (cue.sentence !== null && cue.sentence !== undefined ? `${word_sentence} ${cue.sentence}` : "♪");
					position.hidden = false;
				}catch(e){
					console.warn("show_cue_position error:", e);
				}
			};
		}
		if(typeof(window.show_glassmask) !== "function"){
			window.show_glassmask = function(msg){
				let glassmask = document.querySelector("#gr_glassmask");
				if(!glassmask){
					glassmask = document.createElement("div");
					glassmask.id = "gr_glassmask";
					document.body.appendChild(glassmask);
				}
				glassmask.className = "gr-glass-mask";
				glassmask.innerHTML = `${msg}`;
			};
		}
		if(typeof(window.create_uuid) !== "function"){
			window.create_uuid = function(){
				try{
					return crypto.randomUUID();
				}catch(e){
					return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, c =>{
						const r = Math.random() * 16 | 0;
						const v = c === "x" ? r : (r & 0x3 | 0x8);
						return v.toString(16);
					});
				}
			};
		}
		//////////////////////
		const bc = new BroadcastChannel("E2A-channel");
		const tab_id = create_uuid();
		const currentStorage = localStorage.getItem("data");
		if(currentStorage){
			window.session_storage = JSON.parse(currentStorage);
			window.session_storage.tab_id = tab_id;
			if(window.session_storage.playback_volume === 0){
				window.session_storage.playback_volume = 1.0;
			}
		}else{
			window.session_storage = {};
			window.session_storage.playback_time = 0;
			window.session_storage.playback_volume = 1.0;
		}
		bc.onmessage = (event)=>{
			try{
				const msg = event.data;
				if(!msg || msg.senderId === tab_id){
					return;
				}
				switch (msg.type){
					case "check-existing":
						bc.postMessage({ type: "already-open", senderId: tab_id });
						break;
					case "already-open":
						tabs_open = true;
						break;
					case "new-tab-open":
						show_glassmask(msg.text);
						break;
				}
			}catch(e){
				console.warn("bc.onmessage error:", e);
			}
		};
		window.addEventListener("beforeunload", ()=>{
			try{
				const newStorage = JSON.parse(localStorage.getItem("data") || "{}");
				if(newStorage.tab_id == window.session_storage.tab_id || !newStorage.tab_id){
					delete newStorage.tab_id;
					delete newStorage.status;
					newStorage.playback_time = Number(window.session_storage.playback_time);
					newStorage.playback_volume = parseFloat(window.session_storage.playback_volume);
					localStorage.setItem("data", JSON.stringify(newStorage));
				}
			}catch(e){
				console.warn("Error updating status on unload:", e);
			}
		});
		window.onElementAvailable("input:not([type='hidden']), textarea", (el)=>{
			el.setAttribute("autocomplete", "off");
		}, {once: false});
		window.onElementAvailable("#gr_voice_player_hidden audio", (el)=>{
			return window.init_voice_player_hidden();
		}, {once: false});
		window.onElementAvailable("#gr_audiobook_player audio", (el)=>{
			return window.init_audiobook_player(el);
		}, {once: false});
		window.onElementAvailable("#gr_playback_time input, #gr_playback_time textarea", (el)=>{
			gr_playback_time = el;
		}, {once: false});
		window.onElementAvailable("#gr_audiobook_sentence textarea", (el)=>{
			gr_audiobook_sentence = el;
		}, {once: false});
		window.onElementAvailable("#gr_audiobook_edit_player audio", (el)=>{
			audio_filter = get_audio_filter();
			el.style.transition = "filter 1s ease";
			el.style.filter = audio_filter;
			el.volume = Math.min(Math.max(parseFloat(window.session_storage?.playback_volume) || 1, 0), 1);
			return true;
		}, {once: false});
		// glyph buttons drawn as line icons (header.css [data-icon]): the glyph stays the button text, its icon follows
		// it when the text changes (session switch 🔒/🔑 from the server, voice play ▶/⏸ above). By id first: ▶ is
		// "play" on the voice button but "next" on the blocks pages
		const icon_ids = {gr_blocks_back_btn: "chevron-left", gr_blocks_next_btn: "chevron-right"};
		const icon_glyphs = {"📚": "logo", "▶": "play", "⏸": "pause", "🗑": "trash", "🔒": "lock", "🔑": "key", "◉": "preview", "✔": "check", "✖": "x", "↧": "download", "✎": "edit", "⇄": "rebuild", "↺": "reset", "🔍": "search", "🡅": "upload", "🡄": "arrow-left", "🡆": "arrow-right", "◀": "chevron-left"};
		const set_icon = (el)=>{
			const glyph = (el.textContent || "").replace(/[︎️]/g, "").trim();
			const icon = icon_ids[el.id] || icon_glyphs[glyph];
			if(icon){
				if(el.dataset.icon !== icon){
					el.dataset.icon = icon;
				}
			}else if(el.dataset.icon){
				delete el.dataset.icon;
			}
			return icon;
		};
		window.onElementAvailable("button, .confirm-buttons .btn", (el)=>{
			if(set_icon(el) && !el._icon_observer){
				el._icon_observer = new MutationObserver(()=>set_icon(el));
				el._icon_observer.observe(el, {childList: true, characterData: true, subtree: true});
			}
			return true;
		}, {once: false});
		// voice dropdowns are (re)mounted on visibility changes (block_voice_{i} on each blocks page), so set the placeholder on each mount
		window.onElementAvailable("#gr_voice_list input, .accordion-block-voice-list input", (el)=>{
			el.placeholder = "Internal";
		}, {once: false});
		if (!window._fetch_patched) {
			const originalFetch = window.fetch;
			window._original_fetch = window._original_fetch || originalFetch;
			window.fetch = async function(url, options) {
				if (typeof url === "string" && url.includes("/upload") && options?.body instanceof FormData){
					let has_files = false;
					for(const [, value] of options.body.entries()){
						if(value instanceof File && value.size > 0){
							has_files = true;
							break;
						}
					}
					if(!has_files){
						console.warn("Blocked empty folder upload");
						return new Response(JSON.stringify([]), {
							status: 200,
							headers: {"Content-Type": "application/json"},
						});
					}
				}
				return window._original_fetch.apply(this, arguments);
			};
			window._fetch_patched = true;
		}
		try{
			bc.postMessage({ type: "check-existing", senderId: tab_id });
			setTimeout(()=>{
				if(tabs_open){
					bc.postMessage({
						type: "new-tab-open",
						text: "Session expired.<br/>You can close this window",
						senderId: tab_id
					});
				}
			}, 250);
		}catch(e){
			console.warn("bc.postMessage error:", e);
		}
		return window.session_storage;
	}catch(e){
		console.warn("gr_raed_data js error:", e);
	}
	return null;
}