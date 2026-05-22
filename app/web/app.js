const state = {
  token: localStorage.getItem("feedsystem_token") || "",
  accountId: 0,
  username: "",
  mode: "latest",
  items: [],
  cursor: {},
  selectedVideoId: 0,
};

const els = {
  sessionLabel: document.querySelector("#sessionLabel"),
  logoutBtn: document.querySelector("#logoutBtn"),
  authForm: document.querySelector("#authForm"),
  publishForm: document.querySelector("#publishForm"),
  publishState: document.querySelector("#publishState"),
  publishBtn: document.querySelector("#publishBtn"),
  clearPublishBtn: document.querySelector("#clearPublishBtn"),
  feedList: document.querySelector("#feedList"),
  detailView: document.querySelector("#detailView"),
  detailHint: document.querySelector("#detailHint"),
  refreshBtn: document.querySelector("#refreshBtn"),
  loadMoreBtn: document.querySelector("#loadMoreBtn"),
  toast: document.querySelector("#toast"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function decodeToken(token) {
  if (!token) return {};
  try {
    const payload = token.split(".")[1].replaceAll("-", "+").replaceAll("_", "/");
    return JSON.parse(decodeURIComponent(escape(atob(payload))));
  } catch {
    return {};
  }
}

function syncSession() {
  const claims = decodeToken(state.token);
  state.accountId = Number(claims.account_id || 0);
  state.username = String(claims.username || "");
  els.sessionLabel.textContent = state.token ? `${state.username || "已登录"} #${state.accountId || "-"}` : "未登录";
  els.logoutBtn.classList.toggle("hidden", !state.token);
  els.publishState.textContent = state.token ? "可发布" : "等待登录";
  els.publishBtn.disabled = !state.token;
}

function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.remove("hidden");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => els.toast.classList.add("hidden"), 2600);
}

async function api(path, body = {}, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!(body instanceof FormData)) headers["Content-Type"] = "application/json";
  if (state.token) headers.Authorization = `Bearer ${state.token}`;

  const res = await fetch(path, {
    method: "POST",
    headers,
    body: body instanceof FormData ? body : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || data.detail || `请求失败: ${res.status}`);
  return data;
}

async function upload(path, file) {
  const body = new FormData();
  body.append("file", file);
  return api(path, body);
}

function normalizeVideo(item) {
  const author = item.author || { id: item.author_id, username: item.username };
  return {
    id: Number(item.id),
    authorId: Number(author.id || 0),
    username: author.username || item.username || "未知用户",
    title: item.title || "未命名视频",
    description: item.description || "",
    playUrl: item.play_url || "",
    coverUrl: item.cover_url || "",
    createTime: item.create_time,
    likesCount: Number(item.likes_count || 0),
    isLiked: Boolean(item.is_liked),
  };
}

function formatTime(value) {
  if (!value) return "未知时间";
  const date = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  if (Number.isNaN(date.getTime())) return "未知时间";
  return date.toLocaleString();
}

function renderFeed() {
  els.feedList.innerHTML = "";
  if (!state.items.length) {
    els.feedList.innerHTML = '<div class="empty">还没有视频，发布一个试试。</div>';
    return;
  }

  const html = state.items
    .map((raw) => {
      const item = normalizeVideo(raw);
      return `
        <article class="video-card" data-video-id="${item.id}">
          <video src="${escapeHtml(item.playUrl)}" poster="${escapeHtml(item.coverUrl)}" controls preload="metadata"></video>
          <div class="video-copy">
            <h3 class="video-title">${escapeHtml(item.title)}</h3>
            <p class="video-description">${escapeHtml(item.description || "暂无简介")}</p>
            <div class="meta">
              <span>作者 ${escapeHtml(item.username)} #${item.authorId || "-"}</span>
              <span>${formatTime(item.createTime)}</span>
              <span>${item.likesCount} 赞</span>
            </div>
            <div class="actions">
              <button data-action="detail" data-id="${item.id}" type="button">详情</button>
              <button class="${item.isLiked ? "danger" : "secondary"}" data-action="${item.isLiked ? "unlike" : "like"}" data-id="${item.id}" type="button">
                ${item.isLiked ? "取消赞" : "点赞"}
              </button>
              <button class="ghost" data-action="follow" data-author="${item.authorId}" type="button">关注作者</button>
              <button class="ghost" data-action="unfollow" data-author="${item.authorId}" type="button">取消关注</button>
            </div>
          </div>
        </article>
      `;
    })
    .join("");
  els.feedList.innerHTML = html;
}

function setActiveTab(mode) {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.feed === mode);
  });
}

function feedRequest(reset) {
  const limit = 10;
  if (state.mode === "latest") {
    return ["/feed/listLatest", { limit, latest_time: reset ? 0 : state.cursor.nextTime || 0 }];
  }
  if (state.mode === "popular") {
    if (!reset && state.cursor.asOf) {
      return ["/feed/listByPopularity", { limit, as_of: state.cursor.asOf, offset: state.cursor.nextOffset || 0 }];
    }
    if (!reset && state.cursor.latestBefore) {
      return [
        "/feed/listByPopularity",
        {
          limit,
          latest_popularity: state.cursor.latestPopularity || 0,
          latest_before: state.cursor.latestBefore,
          latest_id_before: state.cursor.latestIdBefore,
        },
      ];
    }
    return ["/feed/listByPopularity", { limit, as_of: 0, offset: 0 }];
  }
  if (state.mode === "likes") {
    const body = { limit };
    if (!reset && state.cursor.likesBefore !== undefined) {
      body.likes_count_before = state.cursor.likesBefore;
      body.id_before = state.cursor.idBefore;
    }
    return ["/feed/listLikesCount", body];
  }
  if (state.mode === "following") {
    return ["/feed/listByFollowing", { limit, latest_time: reset ? 0 : state.cursor.nextTime || 0 }];
  }
  return ["/like/listMyLikedVideos", {}];
}

function updateCursor(data) {
  state.cursor = {
    hasMore: Boolean(data.has_more),
    nextTime: data.next_time || 0,
    asOf: data.as_of || 0,
    nextOffset: data.next_offset || 0,
    latestPopularity: data.next_latest_popularity || 0,
    latestBefore: data.next_latest_before || "",
    latestIdBefore: data.next_latest_id_before || 0,
    likesBefore: data.next_likes_count_before,
    idBefore: data.next_id_before,
  };
  els.loadMoreBtn.disabled = !state.cursor.hasMore || state.mode === "mine";
  els.loadMoreBtn.textContent = state.cursor.hasMore && state.mode !== "mine" ? "加载更多" : "没有更多";
}

async function loadFeed(reset = true) {
  if ((state.mode === "following" || state.mode === "mine") && !state.token) {
    state.items = [];
    updateCursor({ has_more: false });
    renderFeed();
    showToast("请先登录");
    return;
  }

  els.loadMoreBtn.disabled = true;
  els.loadMoreBtn.textContent = "加载中";
  try {
    const [path, body] = feedRequest(reset);
    const data = await api(path, body);
    const rows = Array.isArray(data) ? data : data.video_list || [];
    state.items = reset ? rows : state.items.concat(rows);
    updateCursor(Array.isArray(data) ? { has_more: false } : data);
    renderFeed();
  } catch (err) {
    showToast(err.message);
    if (reset) {
      state.items = [];
      updateCursor({ has_more: false });
      renderFeed();
    }
  }
}

async function renderDetail(videoId) {
  state.selectedVideoId = Number(videoId);
  els.detailView.innerHTML = '<div class="detail-empty">加载中</div>';
  try {
    const [video, comments] = await Promise.all([
      api("/video/getDetail", { id: state.selectedVideoId }),
      api("/comment/listAll", { video_id: state.selectedVideoId }),
    ]);
    const item = normalizeVideo(video);
    els.detailHint.textContent = `${item.title} 的评论`;
    const commentHtml = comments.length
      ? comments
          .map((comment) => {
            const canDelete = Number(comment.author_id) === state.accountId;
            return `
              <div class="comment">
                <strong>${escapeHtml(comment.username)} #${Number(comment.author_id || 0)}</strong>
                <span class="meta">${formatTime(comment.created_at)}</span>
                <p>${escapeHtml(comment.content)}</p>
                ${canDelete ? `<button class="ghost" data-action="delete-comment" data-comment-id="${comment.id}" type="button">删除</button>` : ""}
              </div>
            `;
          })
          .join("")
      : '<div class="empty">暂无评论</div>';

    els.detailView.innerHTML = `
      <div class="detail-content">
        <video class="detail-video" src="${escapeHtml(item.playUrl)}" poster="${escapeHtml(item.coverUrl)}" controls></video>
        <div>
          <h3 class="video-title">${escapeHtml(item.title)}</h3>
          <p class="video-description">${escapeHtml(item.description || "暂无简介")}</p>
          <div class="meta">
            <span>作者 ${escapeHtml(item.username)} #${item.authorId || "-"}</span>
            <span>${item.likesCount} 赞</span>
          </div>
        </div>
        <form id="commentForm" class="comment-form">
          <div class="field">
            <label for="commentContent">发表评论</label>
            <textarea id="commentContent" rows="3" maxlength="300" placeholder="写下你的看法"></textarea>
          </div>
          <button type="submit">发送评论</button>
        </form>
        <div class="comment-list">${commentHtml}</div>
      </div>
    `;
  } catch (err) {
    els.detailView.innerHTML = `<div class="detail-empty">${escapeHtml(err.message)}</div>`;
  }
}

async function handleAuth(action) {
  const username = document.querySelector("#username").value.trim();
  const password = document.querySelector("#password").value;
  if (!username || !password) {
    showToast("请输入用户名和密码");
    return;
  }
  try {
    if (action === "register") {
      await api("/account/register", { username, password });
      showToast("注册成功，请登录");
      return;
    }
    const data = await api("/account/login", { username, password });
    state.token = data.token || "";
    localStorage.setItem("feedsystem_token", state.token);
    syncSession();
    showToast("登录成功");
    await loadFeed(true);
  } catch (err) {
    showToast(err.message);
  }
}

async function handlePublish(event) {
  event.preventDefault();
  if (!state.token) {
    showToast("请先登录");
    return;
  }
  const title = document.querySelector("#title").value.trim();
  const description = document.querySelector("#description").value.trim();
  const videoFile = document.querySelector("#videoFile").files[0];
  const coverFile = document.querySelector("#coverFile").files[0];
  if (!title || !videoFile || !coverFile) {
    showToast("标题、视频和封面都需要填写");
    return;
  }

  els.publishBtn.disabled = true;
  els.publishState.textContent = "上传中";
  try {
    const video = await upload("/video/uploadVideo", videoFile);
    const cover = await upload("/video/uploadCover", coverFile);
    await api("/video/publish", {
      title,
      description,
      play_url: video.play_url || video.url,
      cover_url: cover.cover_url || cover.url,
    });
    event.target.reset();
    els.publishState.textContent = "已发布";
    showToast("发布成功");
    state.mode = "latest";
    setActiveTab("latest");
    await loadFeed(true);
  } catch (err) {
    showToast(err.message);
  } finally {
    els.publishBtn.disabled = !state.token;
    if (state.token) els.publishState.textContent = "可发布";
  }
}

async function handleFeedAction(target) {
  if (!target) return;
  const action = target.dataset.action;
  if (!action) return;
  const id = Number(target.dataset.id || 0);
  try {
    if (action === "detail") {
      await renderDetail(id);
      return;
    }
    if (!state.token) {
      showToast("请先登录");
      return;
    }
    if (action === "like" || action === "unlike") {
      await api(`/like/${action}`, { video_id: id });
      showToast(action === "like" ? "点赞成功" : "已取消点赞");
      await loadFeed(true);
      if (state.selectedVideoId === id) await renderDetail(id);
      return;
    }
    if (action === "follow" || action === "unfollow") {
      const authorId = Number(target.dataset.author || 0);
      if (!authorId || authorId === state.accountId) {
        showToast("不能关注自己");
        return;
      }
      await api(`/social/${action}`, { vlogger_id: authorId });
      showToast(action === "follow" ? "已关注作者" : "已取消关注");
    }
  } catch (err) {
    showToast(err.message);
  }
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", async () => {
    state.mode = tab.dataset.feed;
    setActiveTab(state.mode);
    await loadFeed(true);
  });
});

els.authForm.addEventListener("submit", (event) => {
  event.preventDefault();
  handleAuth(event.submitter?.dataset.auth || "login");
});

els.logoutBtn.addEventListener("click", async () => {
  try {
    await api("/account/logout", {});
  } catch {
    // Local logout still clears stale tokens when the server already revoked them.
  }
  state.token = "";
  state.accountId = 0;
  state.username = "";
  localStorage.removeItem("feedsystem_token");
  syncSession();
  showToast("已退出");
  await loadFeed(true);
});

els.publishForm.addEventListener("submit", handlePublish);
els.clearPublishBtn.addEventListener("click", () => els.publishForm.reset());
els.refreshBtn.addEventListener("click", () => loadFeed(true));
els.loadMoreBtn.addEventListener("click", () => loadFeed(false));
els.feedList.addEventListener("click", (event) => handleFeedAction(event.target.closest("button")));

els.detailView.addEventListener("submit", async (event) => {
  if (event.target.id !== "commentForm") return;
  event.preventDefault();
  if (!state.token) {
    showToast("请先登录");
    return;
  }
  const content = document.querySelector("#commentContent").value.trim();
  if (!content) {
    showToast("请输入评论内容");
    return;
  }
  try {
    await api("/comment/publish", { video_id: state.selectedVideoId, content });
    showToast("评论已发布");
    await renderDetail(state.selectedVideoId);
  } catch (err) {
    showToast(err.message);
  }
});

els.detailView.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action='delete-comment']");
  if (!button) return;
  try {
    await api("/comment/delete", { comment_id: Number(button.dataset.commentId) });
    showToast("评论已删除");
    await renderDetail(state.selectedVideoId);
  } catch (err) {
    showToast(err.message);
  }
});

syncSession();
loadFeed(true);
