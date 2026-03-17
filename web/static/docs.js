(function () {
  function token() {
    var v = localStorage.getItem("rag_token");
    if (v) return v;
    return "";
  }
  function authHeader() {
    return { Authorization: "Bearer " + token() };
  }
  function jsonHeaders() {
    return { "Content-Type": "application/json", Authorization: "Bearer " + token() };
  }
  function el(tag, cls) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    return e;
  }
  function toast(node, text, isErr) {
    node.style.display = "block";
    node.className = "toast " + (isErr ? "error" : "ok");
    node.textContent = text;
  }
  function errMsg(data, defMsg) {
    if (data && data.detail) return String(data.detail);
    return defMsg;
  }
  function exMsg(e, defMsg) {
    if (e) {
      if (e.message) return String(e.message);
      return String(e);
    }
    return defMsg;
  }
  function ensureAuthed(resp) {
    if (resp && resp.status === 401) {
      localStorage.removeItem("rag_token");
      window.location.href = "/login";
      return false;
    }
    return true;
  }

  function mount() {
    var t = token();
    if (!t) return;
    var container = document.querySelector(".container");
    var layout = document.querySelector(".layout");
    if (!container || !layout) return;

    var card = el("div", "card pad");
    card.style.marginBottom = "16px";

    var row = el("div", "row wrap");
    row.style.gap = "12px";

    var left = el("div");
    var m = el("div", "muted");
    m.textContent = "文档管理";
    var tip = el("div");
    tip.style.marginTop = "6px";
    tip.textContent = "上传txt/md/pdf后点击构建向量库";
    left.appendChild(m);
    left.appendChild(tip);

    var spacer = el("div", "spacer");

    var input = el("input", "input");
    input.type = "file";
    input.style.maxWidth = "380px";

    var btnUp = el("button", "btn");
    btnUp.textContent = "上传";
    var btnBuild = el("button", "btn primary");
    btnBuild.textContent = "构建向量库";

    row.appendChild(left);
    row.appendChild(spacer);
    row.appendChild(input);
    row.appendChild(btnUp);
    row.appendChild(btnBuild);

    var st = el("div", "toast");
    st.style.display = "none";

    var lbl = el("div", "muted");
    lbl.style.marginTop = "10px";
    lbl.textContent = "已上传文件";

    var list = el("div", "list");
    list.style.maxHeight = "140px";

    card.appendChild(row);
    card.appendChild(st);
    card.appendChild(lbl);
    card.appendChild(list);
    container.insertBefore(card, layout);

    function deleteFile(name) {
      if (!name) return Promise.resolve();
      if (!window.confirm("确认删除文件：\n" + name + "\n\n提示：若已构建向量库，删除后需要重新点击“构建向量库”才会在检索中生效。")) {
        return Promise.resolve();
      }

      return fetch("/docs/files?name=" + encodeURIComponent(name), { method: "DELETE", headers: jsonHeaders() })
        .then(function (r) {
          if (!ensureAuthed(r)) return {};
          return r
            .json()
            .catch(function () {
              return {};
            })
            .then(function (d) {
              if (!r.ok) throw new Error(errMsg(d, "删除失败"));
              return d;
            });
        })
        .then(function () {
          toast(st, "已删除：" + name, false);
          return loadFiles();
        })
        .catch(function (e) {
          toast(st, exMsg(e, "删除失败"), true);
        });
    }

    function loadFiles() {
      return fetch("/docs/files", { headers: jsonHeaders() })
        .then(function (r) {
          if (!ensureAuthed(r)) return [];
          return r
            .json()
            .catch(function () {
              return [];
            })
            .then(function (d) {
              if (!r.ok) throw new Error(errMsg(d, "加载文件失败"));

              list.innerHTML = "";
              if (!d.length) {
                var x = el("div", "muted");
                x.textContent = "暂无文件";
                list.appendChild(x);
                return;
              }

              for (var i = 0; i != d.length; i++) {
                (function () {
                  var f = d[i];
                  var it = el("div", "item");
                  it.style.cursor = "default";

                  var top = el("div", "row");
                  top.style.gap = "10px";

                  var nameWrap = el("div");
                  nameWrap.style.flex = "1";

                  var n = el("div");
                  n.style.fontWeight = "700";
                  n.textContent = f.name ? String(f.name) : "";

                  var z = el("div", "muted");
                  z.style.marginTop = "4px";
                  z.style.fontSize = "12px";
                  z.textContent = String(f.size ? f.size : 0) + " bytes";

                  nameWrap.appendChild(n);
                  nameWrap.appendChild(z);

                  var btnDel = el("button", "btn danger sm");
                  btnDel.textContent = "删除";
                  btnDel.addEventListener("click", function (ev) {
                    ev.preventDefault();
                    ev.stopPropagation();
                    deleteFile(f.name ? String(f.name) : "");
                  });

                  top.appendChild(nameWrap);
                  top.appendChild(btnDel);
                  it.appendChild(top);
                  list.appendChild(it);
                })();
              }
            });
        })
        .catch(function (e) {
          toast(st, exMsg(e, "加载文件失败"), true);
        });
    }

    function refreshStatus() {
      return fetch("/docs/status", { headers: jsonHeaders() })
        .then(function (r) {
          if (!ensureAuthed(r)) return {};
          return r
            .json()
            .catch(function () {
              return {};
            });
        })
        .then(function (s) {
          if (!s || !s.state) return;
          if (s.state === "running") {
            btnBuild.disabled = true;
            toast(st, s.message ? s.message : "正在构建...", false);
            return;
          }
          if (s.state === "ok") {
            btnBuild.disabled = false;
            toast(st, s.message ? s.message : "构建完成", false);
            return;
          }
          if (s.state === "error") {
            btnBuild.disabled = false;
            toast(st, s.message ? s.message : "构建失败", true);
            return;
          }
          btnBuild.disabled = false;
        })
        .catch(function () {});
    }

    btnUp.addEventListener("click", function () {
      if (!input.files || !input.files.length) {
        toast(st, "请选择文件", true);
        return;
      }

      btnUp.disabled = true;
      var fd = new FormData();
      fd.append("file", input.files[0]);
      fetch("/docs/upload", { method: "POST", headers: authHeader(), body: fd })
        .then(function (r) {
          if (!ensureAuthed(r)) return {};
          return r
            .json()
            .catch(function () {
              return {};
            })
            .then(function (d) {
              if (!r.ok) throw new Error(errMsg(d, "上传失败"));
              return d;
            });
        })
        .then(function () {
          input.value = "";
          toast(st, "上传成功", false);
          return loadFiles();
        })
        .catch(function (e) {
          toast(st, exMsg(e, "上传失败"), true);
        })
        .finally(function () {
          btnUp.disabled = false;
        });
    });

    var timer = null;
    btnBuild.addEventListener("click", function () {
      btnBuild.disabled = true;
      fetch("/docs/build", { method: "POST", headers: jsonHeaders() })
        .then(function (r) {
          if (!ensureAuthed(r)) return {};
          return r
            .json()
            .catch(function () {
              return {};
            })
            .then(function (d) {
              if (!r.ok) throw new Error(errMsg(d, "触发构建失败"));
              return d;
            });
        })
        .then(function () {
          toast(st, "已开始构建...", false);
          if (timer) {
            clearInterval(timer);
            timer = null;
          }
          timer = setInterval(function () {
            refreshStatus().then(function () {
              return fetch("/docs/status", { headers: jsonHeaders() })
                .then(function (r) {
                  if (!ensureAuthed(r)) return {};
                  return r
                    .json()
                    .catch(function () {
                      return {};
                    });
                })
                .then(function (s) {
                  if (!s || !s.state) return;
                  if (s.state === "running") return;
                  clearInterval(timer);
                  timer = null;
                  btnBuild.disabled = false;
                  loadFiles();
                });
            });
          }, 1000);
        })
        .catch(function (e) {
          btnBuild.disabled = false;
          toast(st, exMsg(e, "触发构建失败"), true);
        });
    });

    loadFiles();
    refreshStatus();
  }

  window.addEventListener("DOMContentLoaded", mount);
})();

