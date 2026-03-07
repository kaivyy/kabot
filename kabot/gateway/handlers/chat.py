"""Chat panel handlers: chat partial, chat log, chat API, chat action, chat stream."""

from __future__ import annotations

import asyncio
import html
import json

from aiohttp import web


class ChatMixin:
    async def handle_dashboard_chat(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        enabled = self._dashboard_write_enabled(request)
        disabled_attr = "" if enabled else " disabled"
        input_disabled_attr = "" if enabled else " disabled"
        session_key = self._resolve_session_key(request.query.get("session_key"))
        channel_name = str(request.query.get("channel") or "dashboard").strip() or "dashboard"
        chat_id = str(request.query.get("chat_id") or "dashboard").strip() or "dashboard"
        config_snapshot = self._status_config()
        runtime_snapshot = (
            config_snapshot.get("runtime", {})
            if isinstance(config_snapshot, dict)
            else {}
        )
        runtime_model = (
            runtime_snapshot.get("model", {})
            if isinstance(runtime_snapshot, dict)
            else {}
        )
        default_model = (
            str(runtime_model.get("primary") or "").strip()
            if isinstance(runtime_model, dict)
            else ""
        )
        default_fallbacks = (
            runtime_model.get("fallbacks", [])
            if isinstance(runtime_model, dict)
            else []
        )
        if not isinstance(default_fallbacks, list):
            default_fallbacks = []
        providers_snapshot = (
            config_snapshot.get("providers", {})
            if isinstance(config_snapshot, dict)
            else {}
        )
        available_providers = (
            providers_snapshot.get("available", [])
            if isinstance(providers_snapshot, dict)
            else []
        )
        configured_providers = (
            providers_snapshot.get("configured", [])
            if isinstance(providers_snapshot, dict)
            else []
        )
        models_by_provider_raw = (
            providers_snapshot.get("models_by_provider", {})
            if isinstance(providers_snapshot, dict)
            else {}
        )
        model_map: dict[str, list[str]] = {}
        if isinstance(models_by_provider_raw, dict):
            for provider_name, models in models_by_provider_raw.items():
                provider_key = str(provider_name).strip().lower()
                if not provider_key:
                    continue
                if isinstance(models, list):
                    cleaned = [str(item).strip() for item in models if str(item).strip()]
                else:
                    cleaned = []
                if cleaned:
                    model_map[provider_key] = cleaned[:200]
        available_provider_names = sorted(
            {
                str(item).strip().lower()
                for item in available_providers
                if str(item).strip()
            }
        )
        if model_map:
            available_provider_names = sorted(
                set(available_provider_names).union(set(model_map.keys()))
            )
        configured_provider_names = {
            str(item).strip().lower()
            for item in configured_providers
            if str(item).strip()
        }
        requested_provider = str(request.query.get("provider") or "").strip().lower()
        requested_model = str(request.query.get("model") or "").strip()
        requested_fallbacks = str(request.query.get("fallbacks") or "").strip()
        selected_provider = requested_provider
        selected_model = requested_model or default_model
        if not selected_provider and "/" in selected_model:
            selected_provider = selected_model.split("/", 1)[0].strip().lower()
        selected_fallbacks = requested_fallbacks or ",".join(
            [str(item).strip() for item in default_fallbacks if str(item).strip()]
        )
        post_url = self._dashboard_url_with_token("/dashboard/partials/chat", request)
        log_url = self._dashboard_url_with_token(
            "/dashboard/partials/chat/log",
            request,
            query={"session_key": session_key},
        )
        provider_options = ["<option value=''>auto</option>"]
        for provider_name in available_provider_names:
            selected_attr = " selected" if provider_name == selected_provider else ""
            configured_badge = " (configured)" if provider_name in configured_provider_names else ""
            provider_options.append(
                f"<option value='{html.escape(provider_name)}'{selected_attr}>"
                f"{html.escape(provider_name + configured_badge)}</option>"
            )

        suggestion_models: list[str] = []
        if selected_provider and selected_provider in model_map:
            suggestion_models = model_map.get(selected_provider, [])
        elif model_map:
            # If provider is not selected yet, show a small merged shortlist.
            merged: list[str] = []
            for models in model_map.values():
                for model_id in models:
                    if model_id in merged:
                        continue
                    merged.append(model_id)
                    if len(merged) >= 200:
                        break
                if len(merged) >= 200:
                    break
            suggestion_models = merged
        datalist_options = "".join(
            f"<option value='{html.escape(model_id)}'></option>"
            for model_id in suggestion_models[:200]
        )
        model_map_json = html.escape(json.dumps(model_map, ensure_ascii=False))
        read_only_note = ""
        if callable(self.control_handler) and not enabled:
            read_only_note = (
                "<div style='padding:10px 16px;border-top:1px solid var(--border,#222635);"
                "border-bottom:1px solid var(--border,#222635);background:rgba(245,158,11,.08);"
                "font-size:11px;color:var(--muted,#8b92a5);'>"
                "Read-only token detected. Sending chat requires "
                "<span class='mono'>operator.write</span>."
                "</div>"
            )

        fragment = (
            "<style>"
            "@keyframes kb-pulse{0%,100%{opacity:1}50%{opacity:.4}}"
            "@keyframes kb-fadein{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}"
            ".kb-msg-row{animation:kb-fadein .25s ease both}"
            ".kb-bubble{max-width:78%;padding:11px 15px;font-size:13.5px;line-height:1.6;word-break:break-word;white-space:pre-wrap;border-radius:16px;position:relative;}"
            ".kb-bubble.user{background:linear-gradient(135deg,#0ea5e9,#0284c7);color:#fff;border-bottom-right-radius:4px;box-shadow:0 4px 14px rgba(14,165,233,.35);}"
            ".kb-bubble.agent{background:var(--bg-elevated,#11141d);border:1px solid var(--border,#222635);color:var(--text,#f0f3f9);border-bottom-left-radius:4px;box-shadow:0 2px 8px rgba(0,0,0,.25);font-family:ui-monospace,monospace;font-size:12.5px;}"
            ".kb-bubble.status{background:rgba(14,165,233,.08);border:1px dashed rgba(14,165,233,.28);color:var(--text,#f0f3f9);border-radius:12px;font-family:inherit;font-size:12px;}"
            ".kb-avatar{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0;letter-spacing:0;}"
            ".kb-avatar.user{background:linear-gradient(135deg,#0ea5e9,#6366f1);color:#fff;}"
            ".kb-avatar.agent{background:linear-gradient(135deg,#1e293b,#334155);color:#94a3b8;border:1px solid var(--border,#222635);}"
            ".kb-ts{font-size:10px;color:var(--muted,#8b92a5);margin-top:4px;}"
            ".kb-phase-badge{display:inline-flex;align-items:center;gap:4px;border-radius:999px;padding:2px 8px;font-size:10px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;background:rgba(14,165,233,.12);color:#7dd3fc;border:1px solid rgba(14,165,233,.25);}"
            ".kb-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;height:100%;color:var(--muted,#8b92a5);}"
            ".kb-empty-icon{width:52px;height:52px;border-radius:50%;background:var(--bg-elevated,#11141d);border:1px solid var(--border,#222635);display:flex;align-items:center;justify-content:center;font-size:24px;animation:kb-pulse 3s ease infinite;}"
            ".kb-cfg-panel{position:absolute;right:0;top:calc(100% + 8px);width:300px;padding:16px;background:rgba(17,20,29,.95);border:1px solid var(--border,#222635);border-radius:12px;box-shadow:0 20px 60px rgba(0,0,0,.5);backdrop-filter:blur(12px);z-index:50;}"
            ".kb-tag{display:inline-flex;align-items:center;gap:4px;border:1px solid var(--border,#222635);border-radius:20px;padding:2px 8px;background:var(--bg,#000);font-size:10px;cursor:default;}"
            "</style>"
            "<div style='display:flex;flex-direction:column;height:100%;background:var(--panel,#0a0c10);border-radius:12px;overflow:hidden;border:1px solid var(--border,#222635);'>"

            # â”€â”€ Header â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            "<div style='display:flex;align-items:center;justify-content:space-between;padding:14px 18px;"
            "background:linear-gradient(135deg,#0a0c10,#11141d);border-bottom:1px solid var(--border,#222635);flex-shrink:0;'>"
            "  <div style='display:flex;align-items:center;gap:10px;'>"
            "    <div style='position:relative;'>"
            "      <div style='width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#0ea5e9,#6366f1);"
            "           display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:700;color:white;box-shadow:0 0 16px rgba(14,165,233,.4);'>K</div>"
            "      <div style='position:absolute;bottom:0;right:0;width:10px;height:10px;border-radius:50%;background:#10b981;"
            "           border:2px solid var(--panel,#0a0c10);box-shadow:0 0 6px #10b981;animation:kb-pulse 2s ease infinite;'></div>"
            "    </div>"
            "    <div>"
            "      <div style='font-size:13px;font-weight:600;color:var(--text,#f0f3f9);'>Kabot Agent</div>"
            f"     <div style='font-size:10px;color:var(--muted,#8b92a5);font-family:monospace;margin-top:1px;'>{html.escape(session_key)}</div>"
            "    </div>"
            "  </div>"
            "  <details class='relative' style='position:relative;'>"
            "    <summary style='list-style:none;cursor:pointer;padding:7px;border-radius:8px;"
            "             border:1px solid transparent;transition:all .2s;' "
            "             onmouseover=\"this.style.borderColor='var(--border)';this.style.background='var(--bg-hover)';\""
            "             onmouseout=\"this.style.borderColor='transparent';this.style.background='';\">"
            "      <svg width='18' height='18' fill='none' stroke='#8b92a5' viewBox='0 0 24 24'>"
            "        <path stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M10.325 4.317c.426-1.756 2.924-1.756 "
            "3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 "
            "3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 "
            "0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 "
            "1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065zM15 12a3 3 0 11-6 0 3 3 0 016 0z'/>"
            "      </svg>"
            "    </summary>"
            "    <div class='kb-cfg-panel'>"
            "      <div style='font-size:12px;font-weight:600;margin-bottom:12px;padding-bottom:10px;border-bottom:1px solid var(--border,#222635);"
            "           display:flex;align-items:center;gap:6px;'>"
            "        <svg width='14' height='14' fill='none' stroke='#0ea5e9' viewBox='0 0 24 24'>"
            "          <path stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 "
            "2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18'/>"
            "        </svg> Model Configuration"
            "      </div>"
            "      <div style='display:flex;flex-direction:column;gap:10px;'>"
            "        <div>"
            "          <label style='font-size:10px;font-weight:600;color:#0ea5e9;text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:5px;'>Provider</label>"
            f"         <select form='chat-form' name='provider' style='width:100%;font-size:12px;background:var(--bg,#000);border-radius:8px;padding:7px 10px;' {input_disabled_attr}>{''.join(provider_options)}</select>"
            "        </div>"
            "        <div>"
            "          <label style='font-size:10px;font-weight:600;color:#0ea5e9;text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:5px;'>Model</label>"
            f"         <input form='chat-form' name='model' style='width:100%;font-size:12px;background:var(--bg,#000);border-radius:8px;padding:7px 10px;box-sizing:border-box;'"
            f"                value='{html.escape(selected_model)}' list='model-suggestions' data-model-map=\"{model_map_json}\" {input_disabled_attr} placeholder='e.g. gpt-4o' />"
            f"         <datalist id='model-suggestions'>{datalist_options}</datalist>"
            "        </div>"
            "        <div>"
            "          <label style='font-size:10px;font-weight:600;color:#0ea5e9;text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:5px;'>Fallbacks</label>"
            "          <div id='fallback-builder'>"
            f"           <input form='chat-form' type='hidden' name='fallbacks' value='{html.escape(selected_fallbacks)}' />"
            "            <div style='display:flex;gap:6px;'>"
            f"             <input id='fallback-input' type='text' placeholder='model/alias' {input_disabled_attr}"
            "                    style='flex:1;font-size:12px;background:var(--bg,#000);border-radius:8px;padding:6px 10px;' />"
            f"             <button id='fallback-add-btn' type='button'{disabled_attr}"
            "                     style='padding:6px 12px;font-size:11px;border-radius:8px;background:#0ea5e9;white-space:nowrap;'>+ Add</button>"
            "            </div>"
            "            <div id='fallback-items' style='display:flex;flex-wrap:wrap;gap:4px;margin-top:6px;'></div>"
            "          </div>"
            "        </div>"
            "        <div style='padding-top:10px;border-top:1px solid var(--border,#222635);'>"
            "          <button type='button' id='config-save-btn'"
            "                  style='width:100%;padding:9px;border-radius:8px;background:linear-gradient(135deg,#10b981,#059669);"
            "                         color:white;font-size:12px;font-weight:600;border:none;cursor:pointer;transition:opacity .2s;'"
            "                  onmouseover=\"this.style.opacity='.85'\" onmouseout=\"this.style.opacity='1'\">Save Configuration</button>"
            "        </div>"
            "      </div>"
            "    </div>"
            "  </details>"
            "</div>"
            f"{read_only_note}"

            # â”€â”€ Chat Log â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            f"<div id='chat-log' style='flex:1;overflow-y:auto;padding:20px 16px;display:flex;flex-direction:column;gap:16px;"
            f"background:var(--bg,#000);scroll-behavior:smooth;'"
            f"hx-get='{html.escape(log_url)}' hx-trigger='load, every 3s' hx-swap='innerHTML'>"
            "  <div class='kb-empty'>"
            "    <div class='kb-empty-icon'>ðŸ’¬</div>"
            "    <div style='text-align:center;'>"
            "      <div style='font-size:14px;font-weight:600;margin-bottom:4px;color:var(--text,#f0f3f9);'>Ready to chat</div>"
            "      <div style='font-size:12px;'>Connecting to session stream...</div>"
            "    </div>"
            "  </div>"
            "</div>"

            # â”€â”€ Input Form â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            f"<form id='chat-form' hx-include=\"[name='provider'], [name='model'], [name='fallbacks']\""
            f"      style='padding:14px 16px;background:var(--bg-accent,#0f121a);border-top:1px solid var(--border,#222635);flex-shrink:0;'"
            f"      hx-post='{html.escape(post_url)}' hx-target='#chat-result' hx-swap='innerHTML'>"
            f"  <input type='hidden' name='session_key' value='{html.escape(session_key)}' />"
            f"  <input type='hidden' name='channel' value='{html.escape(channel_name)}' />"
            f"  <input type='hidden' name='chat_id' value='{html.escape(chat_id)}' />"
            "  <div style='display:flex;align-items:flex-end;gap:10px;background:var(--bg,#000);border:1px solid var(--border,#222635);"
            "              border-radius:14px;padding:10px 12px;transition:border-color .2s,box-shadow .2s;'"
            "       onfocusin=\"this.style.borderColor='#0ea5e9';this.style.boxShadow='0 0 0 3px rgba(14,165,233,.15)';\" "
            "       onfocusout=\"this.style.borderColor='var(--border)';this.style.boxShadow='none';\">"
            "    <textarea name='prompt' rows='1' style='flex:1;background:transparent;border:none;color:var(--text,#f0f3f9);font-size:13.5px;"
            "              resize:none;outline:none;padding:2px 0;line-height:1.5;max-height:120px;box-shadow:none;font-family:inherit;'"
            f"              {input_disabled_attr}"
            "              placeholder='Message Kabot...' oninput='this.style.height=\"\";this.style.height=Math.min(this.scrollHeight,120)+\"px\"'"
            "              onkeydown=\"if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();this.closest('form').requestSubmit();}\"></textarea>"
            f"   <button type='submit' style='width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,#0ea5e9,#0284c7);"
            f"           color:white;display:flex;align-items:center;justify-content:center;flex-shrink:0;border:none;cursor:pointer;"
            f"           transition:all .2s;box-shadow:0 4px 12px rgba(14,165,233,.4);'{disabled_attr}"
            "            onmouseover=\"this.style.transform='scale(1.07)';\" onmouseout=\"this.style.transform='scale(1)';\">"
            "      <svg width='16' height='16' fill='none' stroke='currentColor' viewBox='0 0 24 24'>"
            "        <path stroke-linecap='round' stroke-linejoin='round' stroke-width='2.5' d='M5 12h14M12 5l7 7-7 7'/>"
            "      </svg>"
            "   </button>"
            "  </div>"
            "  <div id='chat-result' style='margin-top:6px;font-size:11px;text-align:center;font-family:monospace;min-height:14px;color:var(--muted,#8b92a5);'></div>"
            "</form>"
            "<script>(function(){"
            "var f=document.getElementById('chat-form'); if(!f) return;"
            "f.addEventListener('htmx:afterRequest', function(){"
            "  var ta=f.querySelector('textarea[name=prompt]'); if(ta){ta.value='';ta.style.height='';}"
            "  var cr=document.getElementById('chat-result');"
            "  if(cr) setTimeout(function(){cr.innerHTML='';}, 3000);"
            "  if(window.kabotScrollChatToLatest) window.kabotScrollChatToLatest(true);"
            "});"
            "})();</script>"
            "</div>"

            # â”€â”€ JavaScript â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            f"<script>(function(){{"
            f"var el=document.getElementById('chat-log'); if(!el) return;"
            f"window.__kabotChatState=window.__kabotChatState||{{}};"
            f"var chatStateKey={json.dumps(session_key)};"
            f"var chatState=window.__kabotChatState[chatStateKey]||{{stickToLatest:true,pendingStick:true}};"
            f"window.__kabotChatState[chatStateKey]=chatState;"
            f"window.kabotScrollChatToLatest=function(force){{"
            f"  if(force){{chatState.stickToLatest=true;chatState.pendingStick=true;}}"
            f"  requestAnimationFrame(function(){{"
            f"    var log=document.getElementById('chat-log');"
            f"    if(!log)return;"
            f"    log.scrollTop=log.scrollHeight;"
            f"  }});"
            f"}};"
            f"var chatDistanceFromBottom=function(){{return el.scrollHeight-el.scrollTop-el.clientHeight;}};"
            f"var updateChatStickiness=function(force){{"
            f"  if(force){{chatState.stickToLatest=true;return;}}"
            f"  chatState.stickToLatest=chatDistanceFromBottom()<=40;"
            f"}};"
            f"if(!el.dataset.kabotScrollBound){{"
            f"  el.dataset.kabotScrollBound='1';"
            f"  el.addEventListener('scroll',function(){{updateChatStickiness(false);}});"
            f"  document.body.addEventListener('htmx:beforeSwap',function(evt){{"
            f"    if(evt.target!==el)return;"
            f"    chatState.pendingStick=chatState.stickToLatest||chatDistanceFromBottom()<=40;"
            f"  }});"
            f"  document.body.addEventListener('htmx:afterSwap',function(evt){{"
            f"    if(evt.target!==el)return;"
            f"    if(chatState.pendingStick!==false&&window.kabotScrollChatToLatest)window.kabotScrollChatToLatest(true);"
            f"  }});"
            f"}}"
            f"window.kabotScrollChatToLatest(true);"
            f"var form=document.getElementById('chat-form');"
            f"if(form){{"
            f"  var providerInput=document.querySelector(\"select[name='provider']\");"
            f"  var modelInput=document.querySelector(\"input[name='model']\");"
            f"  var dataList=document.getElementById('model-suggestions');"
            f"  var fallbackHidden=document.querySelector(\"input[name='fallbacks']\");"
            f"  var fallbackInput=document.getElementById('fallback-input');"
            f"  var fallbackItems=document.getElementById('fallback-items');"
            f"  var fallbackAddBtn=document.getElementById('fallback-add-btn');"
            f"  if(providerInput&&modelInput&&dataList){{"
            f"    var rawMap=modelInput.getAttribute('data-model-map')||'{{}}';"
            f"    var modelMap={{}}; try{{modelMap=JSON.parse(rawMap)||{{}};}}catch(_e){{modelMap={{}};}}"
            f"    var escOpt=function(s){{return String(s||'').replace(/[&<>\"']/g,function(c){{return {{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}}[c];}});}};"
            f"    var renderModels=function(){{"
            f"      var provider=String(providerInput.value||'').toLowerCase().trim();"
            f"      var models=[];"
            f"      if(provider&&Array.isArray(modelMap[provider])){{models=modelMap[provider];}}"
            f"      else{{for(var k in modelMap){{if(!Object.prototype.hasOwnProperty.call(modelMap,k))continue;"
            f"        var arr=modelMap[k]; if(!Array.isArray(arr))continue;"
            f"        for(var i=0;i<arr.length;i++){{var m=String(arr[i]||'').trim(); if(!m||models.indexOf(m)!==-1)continue; models.push(m); if(models.length>=200)break;}}"
            f"        if(models.length>=200)break;}}}}"
            f"      dataList.innerHTML=models.slice(0,200).map(function(m){{return \"<option value='\"+escOpt(m)+\"'></option>\";}}).join('');"
            f"    }};"
            f"    providerInput.addEventListener('change',function(){{modelInput.value=''; renderModels();}});"
            f"    renderModels();"
            f"  }}"
            f"  var cfgSaveBtn=document.getElementById('config-save-btn');"
            f"  if(cfgSaveBtn){{"
            f"    cfgSaveBtn.addEventListener('click',function(){{"
            f"      var dt=cfgSaveBtn.closest('details'); if(dt)dt.removeAttribute('open');"
            f"      var o=cfgSaveBtn.textContent; cfgSaveBtn.textContent='âœ“ Saved!';"
            f"      cfgSaveBtn.style.background='linear-gradient(135deg,#10b981,#059669)';"
            f"      setTimeout(function(){{cfgSaveBtn.textContent=o;}},1500);"
            f"    }});"
            f"  }}"
            f"  if(fallbackHidden&&fallbackInput&&fallbackItems&&fallbackAddBtn){{"
            f"    var fallbackList=[];"
            f"    var parseFallbacks=function(raw){{if(!raw)return[];var parts=String(raw).replace(/\\n/g,',').split(',');var out=[];for(var i=0;i<parts.length;i++){{var t=String(parts[i]||'').trim();if(!t||out.indexOf(t)!==-1)continue;out.push(t);if(out.length>=8)break;}}return out;}};"
            f"    var renderFallbacks=function(){{fallbackHidden.value=fallbackList.join(',');if(!fallbackList.length){{fallbackItems.innerHTML='<span style=\"font-size:10px;color:var(--muted);\">No fallbacks.</span>';return;}}fallbackItems.innerHTML=fallbackList.map(function(m,idx){{return '<span class=\"kb-tag\">'+escOpt(m)+'<button type=\"button\" data-fallback-remove=\"'+idx+'\" style=\"border:none;background:transparent;color:var(--muted);cursor:pointer;padding:0;margin-left:2px;font-size:12px;line-height:1;\">Ã—</button></span>';}}).join('');}};"
            f"    var addFallback=function(raw){{var t=String(raw||'').trim();if(!t)return;if(fallbackList.indexOf(t)!==-1){{fallbackInput.value='';return;}}if(fallbackList.length>=8)return;fallbackList.push(t);fallbackInput.value='';renderFallbacks();}};"
            f"    fallbackList=parseFallbacks(fallbackHidden.value);"
            f"    renderFallbacks();"
            f"    fallbackAddBtn.addEventListener('click',function(){{addFallback(fallbackInput.value);}});"
            f"    fallbackInput.addEventListener('keydown',function(ev){{if(ev.key==='Enter'){{ev.preventDefault();addFallback(fallbackInput.value);}}}});"
            f"    fallbackItems.addEventListener('click',function(ev){{var t=ev.target;if(!t||!t.getAttribute)return;var idxRaw=t.getAttribute('data-fallback-remove');if(idxRaw===null||idxRaw==='')return;var idx=parseInt(idxRaw,10);if(Number.isNaN(idx)||idx<0||idx>=fallbackList.length)return;fallbackList.splice(idx,1);renderFallbacks();}});"
            f"  }}"
            f"}}"
            f"if(typeof EventSource!=='undefined'){{"
            f"  window.__kabotChatSSE=window.__kabotChatSSE||{{}};"
            f"  var key={json.dumps(session_key)};"
            f"  if(window.__kabotChatSSE[key]){{try{{window.__kabotChatSSE[key].close();}}catch(_e){{}}}}"
            f"  var url={json.dumps(self._dashboard_url_with_token('/dashboard/api/chat/stream', request, query={'session_key': session_key}))};"
            f"  var es=new EventSource(url); window.__kabotChatSSE[key]=es;"
            f"  function esc(s){{return String(s||'').replace(/[&<>\"']/g,function(c){{return {{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}}[c];}});}}"
            f"  es.addEventListener('snapshot',function(ev){{"
            f"    try{{"
            f"      var p=JSON.parse(ev.data||'{{}}'); var msgs=Array.isArray(p.messages)?p.messages:[];"
            f"      if(!msgs.length){{el.innerHTML='<div class=\"kb-empty\"><div class=\"kb-empty-icon\">ðŸ’¬</div>"
            f"<div style=\"text-align:center;\"><div style=\"font-size:14px;font-weight:600;margin-bottom:4px;color:var(--text);\">No messages yet</div>"
            f"<div style=\"font-size:12px;\">Send a prompt to start chatting</div></div></div>'; if(window.kabotScrollChatToLatest)window.kabotScrollChatToLatest(true); return;}}"
            f"      var rows=[];"
            f"      msgs.slice(-50).forEach(function(m){{"
            f"        var role=esc(m.role||'assistant').toLowerCase(); var ts=esc(m.timestamp||''); var content=esc(m.content||'');"
            f"        var isUser=role==='user';"
            f"        var align=isUser?'flex-end':'flex-start';"
            f"        var avatarLabel=isUser?'U':'K';"
            f"        var avatarClass=isUser?'user':'agent';"
            f"        var bubbleClass=isUser?'kb-bubble user':'kb-bubble agent';"
            f"        var row='<div class=\"kb-msg-row\" style=\"display:flex;flex-direction:column;align-items:'+align+';gap:4px;\">';"
            f"        var avatarRow='<div style=\"display:flex;align-items:center;gap:6px;'+( isUser?'flex-direction:row-reverse;':'')+'\">';"
            f"        avatarRow+='<div class=\"kb-avatar '+avatarClass+'\">'+avatarLabel+'</div>';"
            f"        avatarRow+='<span style=\"font-size:11px;font-weight:600;color:var(--muted);\">'+( isUser?'You':'Kabot')+'</span>';"
            f"        if(ts)avatarRow+='<span class=\"kb-ts\">'+ts+'</span>';"
            f"        avatarRow+='</div>';"
            f"        row+=avatarRow;"
            f"        row+='<div class=\"'+bubbleClass+'\">'+content+'</div>';"
            f"        row+='</div>';"
            f"        rows.push(row);"
            f"      }});"
            f"      chatState.pendingStick=chatState.stickToLatest||chatDistanceFromBottom()<=40;"
            f"      el.innerHTML=rows.join('');"
            f"      if(chatState.pendingStick!==false&&window.kabotScrollChatToLatest)window.kabotScrollChatToLatest(true);"
            f"    }}catch(_err){{}}"
            f"  }});"
            f"}}"
            f"}})();</script>"
        )
        return web.Response(text=fragment, content_type="text/html")

    async def handle_dashboard_chat_history_api(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        session_key = self._resolve_session_key(request.query.get("session_key"))
        limit = self._resolve_history_limit(request.query.get("limit"), default=30)
        items = await self._read_chat_history(session_key, limit=limit)
        return web.json_response({"session_key": session_key, "messages": items})

    async def handle_dashboard_chat_stream_api(self, request: web.Request) -> web.StreamResponse:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized

        session_key = self._resolve_session_key(request.query.get("session_key"))
        limit = self._resolve_history_limit(request.query.get("limit"), default=30)
        once_raw = str(request.query.get("once", "") or "").strip().lower()
        once = once_raw in {"1", "true", "yes", "on"}

        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream; charset=utf-8",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
        await response.prepare(request)

        last_payload = ""
        try:
            while True:
                items = await self._read_chat_history(session_key, limit=limit)
                payload = json.dumps(
                    {"session_key": session_key, "messages": items},
                    ensure_ascii=False,
                )
                if payload != last_payload or once:
                    event_block = f"event: snapshot\ndata: {payload}\n\n"
                    await response.write(event_block.encode("utf-8"))
                    last_payload = payload
                else:
                    await response.write(b"event: ping\ndata: {}\n\n")

                if once:
                    break
                await asyncio.sleep(2.0)
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            try:
                await response.write_eof()
            except Exception:
                pass
        return response

    async def handle_dashboard_chat_log(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        session_key = self._resolve_session_key(request.query.get("session_key"))
        items = await self._read_chat_history(session_key, limit=30)
        if not items:
            fragment = (
                "<div class='kb-empty'>"
                "  <div class='kb-empty-icon'>ðŸ’¬</div>"
                "  <div style='text-align:center;'>"
                "    <div style='font-size:14px;font-weight:600;margin-bottom:4px;color:var(--text,#f0f3f9);'>No messages yet</div>"
                "    <div style='font-size:12px;'>Send a prompt to start chatting</div>"
                "  </div>"
                "</div>"
            )
            return web.Response(text=fragment, content_type="text/html")

        rows: list[str] = []
        for item in items[-50:]:
            role = html.escape(str(item.get("role", "assistant"))).lower()
            timestamp = html.escape(str(item.get("timestamp", "")))
            content = html.escape(str(item.get("content", "")))
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            update_type = str(metadata.get("type") or "").strip().lower()
            phase = html.escape(str(metadata.get("phase") or "").strip().lower())
            is_status_like = update_type in {"status_update", "draft_update", "reasoning_update"}
            is_user = role == "user"
            align = "flex-end" if is_user else "flex-start"
            avatar_label = "U" if is_user else "K"
            avatar_class = "user" if is_user else "agent"
            bubble_class = "kb-bubble user" if is_user else ("kb-bubble status" if is_status_like else "kb-bubble agent")
            flex_dir = "flex-direction:row-reverse;" if is_user else ""
            name_label = "You" if is_user else ("Status" if is_status_like else "Kabot")
            ts_html = f"<span class='kb-ts'>{timestamp}</span>" if timestamp else ""
            phase_badge = f"<span class='kb-phase-badge'>{phase}</span>" if phase else ""
            rows.append(
                f"<div class='kb-msg-row' style='display:flex;flex-direction:column;align-items:{align};gap:4px;'>"
                f"  <div style='display:flex;align-items:center;gap:6px;{flex_dir}'>"
                f"    <div class='kb-avatar {avatar_class}'>{avatar_label}</div>"
                f"    <span style='font-size:11px;font-weight:600;color:var(--muted);'>{name_label}</span>"
                f"    {phase_badge}"
                f"    {ts_html}"
                f"  </div>"
                f"  <div class='{bubble_class}'>{content}</div>"
                f"</div>"
            )
        return web.Response(text="".join(rows), content_type="text/html")

    async def handle_dashboard_chat_api(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        prompt = str(payload.get("prompt") or "").strip() if isinstance(payload, dict) else ""
        session_key = str(payload.get("session_key") or "dashboard:web").strip() if isinstance(payload, dict) else "dashboard:web"
        provider = str(payload.get("provider") or "").strip() if isinstance(payload, dict) else ""
        model = str(payload.get("model") or "").strip() if isinstance(payload, dict) else ""
        fallbacks = payload.get("fallbacks", "") if isinstance(payload, dict) else ""
        channel = str(payload.get("channel") or "dashboard").strip() if isinstance(payload, dict) else "dashboard"
        chat_id = str(payload.get("chat_id") or "dashboard").strip() if isinstance(payload, dict) else "dashboard"
        status_code, result = await self._run_control_action(
            action="chat.send",
            args={
                "prompt": prompt,
                "session_key": session_key,
                "provider": provider,
                "model": model,
                "fallbacks": fallbacks,
                "channel": channel,
                "chat_id": chat_id,
            },
        )
        return web.json_response(result, status=status_code)

    async def handle_dashboard_chat_action(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize_route(request)
        if unauthorized is not None:
            return unauthorized
        data = await request.post()
        prompt = str(data.get("prompt", "") or "").strip()
        session_key = str(data.get("session_key", "") or "dashboard:web").strip()
        provider = str(data.get("provider", "") or "").strip()
        model = str(data.get("model", "") or "").strip()
        fallbacks = str(data.get("fallbacks", "") or "").strip()
        channel = str(data.get("channel", "") or "dashboard").strip()
        chat_id = str(data.get("chat_id", "") or "dashboard").strip()
        status_code, result = await self._run_control_action(
            action="chat.send",
            args={
                "prompt": prompt,
                "session_key": session_key,
                "provider": provider,
                "model": model,
                "fallbacks": fallbacks,
                "channel": channel,
                "chat_id": chat_id,
            },
        )
        if status_code == 200:
            body = "<span style='color:#10b981;'>Success: Action completed. Sent</span>"
        else:
            err_text = ""
            if isinstance(result, dict):
                err_text = str(result.get("message", "")).strip()
            if not err_text:
                err_text = "Failed to send"
            body = f"<span style='color:#ef4444;'>{html.escape(err_text)}</span>"
        return web.Response(text=body, content_type="text/html", status=status_code)


