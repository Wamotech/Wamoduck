function wamoduck_play(mode)
%WAMODUCK_PLAY  Wamoduck 参考步态回放器 / Reference-gait player
%
%   wamoduck_play            打开交互界面（播放/暂停、推进步长、切换轨迹、显示精度）
%   wamoduck_play(true)      无界面自检：检查数据单位、渲一帧存图、打印结论
%   wamoduck_play(8)         冒烟测试：正常开界面，跑 8 秒后自动关闭
%
% 依赖 / Requires: Robotics System Toolbox（importrobot / show） + MATLAB R2021b 或更新
%
% 数据 / Data: tools/matlab/data/*.csv
%   q_* 与 tau_* 分别以 **弧度** 与 **N·m** 给出（不做任何单位换算 —— 少一次换算就少一个 bug），
%   基座位姿为 base_x/base_y/base_z(m) 与 base_roll_rad。
%   见 docs/matlab.zh-CN.md / docs/matlab.en.md。
%
% ⚠️ 本工具只做**运动学回放**（给定关节角 + 正运动学），不含物理积分、不是训练策略、不是实物数据。
%    关节角来自本项目的准静态参考步态规划（逆运动学 + 静态稳定性检查）。

if nargin < 1, mode = false; end
smokeSec = 0;
startMesh = false;
if ischar(mode) || isstring(mode)
    startMesh = strcmpi(string(mode), "mesh");   % wamoduck_play('mesh')：以精细网格启动
    mode = false;
end
if isnumeric(mode) && ~islogical(mode) && mode > 1
    smokeSec = mode;      % 冒烟测试：跑 N 秒后自动关闭
    mode = false;
end
selftest = islogical(mode) && mode;

%% ---------- 路径 / paths ----------
here = fileparts(mfilename('fullpath'));            % <repo>/tools/matlab
root = fileparts(fileparts(here));                  % <repo>
urdfPath = fullfile(root, 'models', 'wmduck', 'wmduck.urdf');
dataDir  = fullfile(here, 'data');
assert(isfile(urdfPath), '找不到 URDF：%s', urdfPath);

% 公开 URDF 的 15 个转动关节（顺序 = 数据列顺序）
JN = ["left_hip_yaw","left_hip_roll","left_hip_pitch","left_knee","left_ankle", ...
      "right_hip_yaw","right_hip_roll","right_hip_pitch","right_knee","right_ankle", ...
      "neck_pitch","head_pitch","head_yaw","head_roll","mouth"];
qcol = "q_" + JN;
tcol = "tau_" + JN;

% 轨迹清单（文件、界面名）
files = {'gait_cycle_2s_50Hz.csv', '一个步态周期 / one gait cycle (2.0 s, 2 cm)'
         'gait_walk_1m_10Hz.csv',  '整段走 1 m / full 1 m walk (104 s, 10 Hz)'};

fprintf('[play] 读取模型 %s\n', urdfPath);
robot = importrobot(urdfPath);
robot.DataFormat = 'column';
q0 = homeConfiguration(robot);

D = struct();
for k = 1:size(files, 1)
    p = fullfile(dataDir, files{k, 1});
    assert(isfile(p), '找不到数据：%s', p);
    % ⚠️ CSV 首行是 '#' 开头的溯源注释，readtable 默认不认 '#'，必须显式指定
    T = readtable(p, 'CommentStyle', '#');
    D.(sprintf('g%d', k)) = T;
    D.(sprintf('n%d', k)) = files{k, 2};
end
tags = {'g1', 'g2'};

%% ---------- 姿态构造（唯一入口 / single source of truth）----------
% ⚠️⚠️ 这里的 q_* **已经是弧度**，所以**不要**再 deg2rad。
% 上一代工具（内部版）曾把"度"直接喂给 show()，每个关节放大 57 倍，
% 导致所有肉眼判断都建立在错画面上（见 docs/matlab.zh-CN.md「踩过的坑」）。
poseAt = @(T, i) local_pose(robot, q0, JN, qcol, T, i);

%% ---------- 自检 / self-test ----------
if selftest
    fprintf('[selftest] 数据单位与几何检查：\n');
    ok = true;
    for k = 1:numel(tags)
        T = D.(tags{k});
        i = round(height(T) / 2);
        q = poseAt(T, i);
        % ① 关节角范围：必须落在 URDF 限位内（否则说明单位错或数据错）
        viol = checkLimits(robot, q);
        % ② 脚底高度：准静态步态的两个脚掌最低点应当在 ±5 mm 量级（单位错会飞到米级）
        zl = soleLowestZ(robot, q, 'left_ankle_link', T.base_z(i));
        zr = soleLowestZ(robot, q, 'right_ankle_link', T.base_z(i));
        fprintf('   %-28s 第 %4d 帧：关节超限 %d 个；脚底高度 左 %+7.2f mm / 右 %+7.2f mm\n', ...
            files{k, 1}, i, viol, zl * 1000, zr * 1000);
        ok = ok && viol == 0 && abs(zl) < 0.02 && abs(zr) < 0.02;
    end
    assert(ok, '自检失败：数据可能不是弧度，或与公开 URDF 不匹配');
    fprintf('[selftest] 通过：数据是弧度、在 URDF 限位内、脚底贴地 ✓\n');

    fig = figure('Visible', 'off', 'Position', [80 80 1100 640]);
    ax = subplot(1, 2, 1, 'Parent', fig);
    T = D.g1;
    q = poseAt(T, round(height(T) / 2));
    show(robot, q, 'Parent', ax, 'PreservePlot', false, 'Frames', 'off');
    title(ax, 'Wamoduck — reference gait, mid-cycle / 参考步态周期中点');
    ax2 = subplot(1, 2, 2, 'Parent', fig);
    plot(ax2, T.t_s, T{:, tcol}, 'LineWidth', 0.9);
    yline(ax2, 3.6, 'r--', 'peak 3.6 N\cdotm'); yline(ax2, -3.6, 'r--');
    yline(ax2, 0.6, 'b:', 'rated 0.6 N\cdotm'); yline(ax2, -0.6, 'b:');
    ylabel(ax2, 'joint torque (N\cdotm)'); xlabel(ax2, 't (s)'); grid(ax2, 'on');
    title(ax2, 'inverse-dynamics estimate / 逆动力学估计');
    out = fullfile(here, 'wamoduck_play_selftest.png');
    exportgraphics(fig, out, 'Resolution', 120);
    close(fig);
    fprintf('[selftest] 已写出 %s\n', out);
    return
end

%% ---------- 交互界面 / interactive UI ----------
fig = figure('Name', 'Wamoduck — reference gait player / 参考步态回放', ...
    'NumberTitle', 'off', 'Tag', 'wamoduckplay', 'Position', [70 50 1360 800], 'Color', 'w');

ax3d  = subplot('Position', [0.030 0.32 0.42 0.62]);
axTau = subplot('Position', [0.515 0.60 0.45 0.34]);
axTab = subplot('Position', [0.515 0.29 0.45 0.28]); axis(axTab, 'off');   % 16 行数值表要放得下

uicontrol(fig, 'Style', 'pushbutton', 'String', '▶ / ⏸', ...
    'Units', 'normalized', 'Position', [0.035 0.20 0.06 0.05], 'FontSize', 12, ...
    'Callback', @(~,~) togglePlay());
uicontrol(fig, 'Style', 'text', 'String', '推进 step', 'Units', 'normalized', ...
    'Position', [0.11 0.205 0.07 0.04], 'BackgroundColor', 'w');
popStep = uicontrol(fig, 'Style', 'popupmenu', ...
    'String', {'1 帧（最连贯）','2 帧','4 帧（默认）','8 帧','16 帧','实时'}, ...
    'Value', 3, 'Units', 'normalized', 'Position', [0.18 0.20 0.13 0.05]);
uicontrol(fig, 'Style', 'text', 'String', '轨迹 data', 'Units', 'normalized', ...
    'Position', [0.32 0.205 0.07 0.04], 'BackgroundColor', 'w');
popGait = uicontrol(fig, 'Style', 'popupmenu', ...
    'String', {D.n1, D.n2}, 'Value', 1, ...
    'Units', 'normalized', 'Position', [0.39 0.20 0.28 0.05], 'FontSize', 10, ...
    'Callback', @(~,~) resetRun());
uicontrol(fig, 'Style', 'text', 'String', '显示 view', 'Units', 'normalized', ...
    'Position', [0.68 0.205 0.07 0.04], 'BackgroundColor', 'w');
popMode = uicontrol(fig, 'Style', 'popupmenu', ...
    'String', {'骨架 skeleton（快）','精细 mesh（慢）'}, 'Value', 1, ...
    'Units', 'normalized', 'Position', [0.75 0.20 0.21 0.05], ...
    'Callback', @(~,~) setMode());
sld = uicontrol(fig, 'Style', 'slider', 'Min', 0, 'Max', 1, 'Value', 0, ...
    'Units', 'normalized', 'Position', [0.035 0.10 0.93 0.04], 'Callback', @(~,~) onSlide());
txtInfo = uicontrol(fig, 'Style', 'text', 'Units', 'normalized', ...
    'Position', [0.035 0.035 0.93 0.05], 'BackgroundColor', 'w', ...
    'HorizontalAlignment', 'left', 'FontSize', 11, 'String', '');

state = struct('playing', true, 'idx', 1, 'tag', 'g1', 'adv', 4, 'nframe', 0, ...
    'groundDrawn', false, 'mode', 'skel', 'hgPrev', [], 'hSkel', [], 'lastT', tic, ...
    'fps', 0, 'tPrev', tic);

% 骨架显示用的常量：脚掌碰撞盒（ankle 连杆系）与机体盒
SOLE_FACES = [1 2 3 4; 5 6 7 8; 1 2 6 5; 2 3 7 6; 3 4 8 7; 4 1 5 8];
SOLE_C = [0,  0.0216, -0.0288
          0, -0.0216, -0.0288];
SOLE_H = [0.0402, 0.0256, 0.0057];
L = 1; R = 2;
% ⚠️ `robot.BodyNames` **不含** base（base 在 robot.BaseName 里），所以机体盒要单独补进去，
% 否则骨架里看不到机体、只有一堆连杆线（第一版就是这样，截图一看很怪）。
skelBodies = [{robot.BaseName}, robot.BodyNames(:)'];
skelParent = cell(size(skelBodies));
skelParent{1} = '';                      % base 的父是世界
for k = 2:numel(skelBodies)
    b = find(strcmp(robot.BodyNames, skelBodies{k}), 1);
    if ~isempty(b) && ~isempty(robot.Bodies{b}.Parent)
        skelParent{k} = robot.Bodies{b}.Parent.Name;
    else
        skelParent{k} = '';
    end
end
nseg = numel(skelBodies);
iAnkL = find(strcmp(skelBodies, 'left_ankle_link'), 1);
iAnkR = find(strcmp(skelBodies, 'right_ankle_link'), 1);
iBase = find(strcmp(skelBodies, 'base_link'), 1);

if startMesh
    state.mode = 'mesh';
    set(popMode, 'Value', 2);
end

resetRun();
drawnow;

% ⚠️ 用 timer 而不是 `while isvalid(fig)` 死循环：后者会把 MATLAB 命令行整个占住。
tmr = timer('ExecutionMode', 'fixedSpacing', 'Period', 0.05, 'BusyMode', 'drop', ...
    'TimerFcn', @(~,~) tick());
set(fig, 'CloseRequestFcn', @(~,~) shutdown());
start(tmr);

if smokeSec > 0
    tSmk = tic;
    smkTmr = timer('ExecutionMode', 'fixedSpacing', 'Period', 0.5, 'BusyMode', 'drop', ...
        'TimerFcn', @(~,~) smokeTick());
    start(smkTmr);
    uiwait(fig);
end

    % ================= 回调 / callbacks =================
    function smokeTick()
        if toc(tSmk) >= smokeSec
            fprintf('[smoke] %.1f s 内渲染 %d 帧 ≈ %.2f fps\n', ...
                toc(tSmk), state.nframe, state.nframe / max(toc(tSmk), 1e-6));
            try, stop(smkTmr); delete(smkTmr); catch, end
            shutdown();
        end
    end

    function tick()
        if ~isvalid(fig), shutdown(); return; end
        if ~state.playing, state.lastT = tic; return; end
        advTab = [1 2 4 8 16 0];
        state.adv = advTab(get(popStep, 'Value'));
        if state.adv == 0
            step = max(1, round(toc(state.lastT) * 50));
        else
            step = state.adv;
        end
        state.lastT = tic;
        state.idx = state.idx + step;
        T = D.(state.tag);
        if state.idx > height(T), state.idx = 1; end
        state.nframe = state.nframe + 1;
        % fps 用"上一帧开始 → 本帧开始"的真实间隔。早先写成 toc(state.lastT)，
        % 而 lastT 刚刚被重置 ⇒ 会算出 4922 fps 这种假数（截图里亲眼看到才发现）。
        dtFrame = toc(state.tPrev); state.tPrev = tic;
        if dtFrame > 1e-3
            state.fps = 0.7 * state.fps + 0.3 / dtFrame;
        end
        render(T);
    end

    function togglePlay()
        state.playing = ~state.playing;
        state.lastT = tic;
    end

    function onSlide()
        T = D.(state.tag);
        state.idx = max(1, min(height(T), round(get(sld, 'Value') * height(T))));
        render(T);
    end

    function setMode()
        m = {'skel', 'mesh'};
        state.mode = m{get(popMode, 'Value')};
        if ishghandle(state.hgPrev), delete(state.hgPrev); state.hgPrev = []; end
        render(D.(state.tag));
    end

    function resetRun()
        v = get(popGait, 'Value');
        state.tag = tags{v};
        state.idx = 1;
        state.lastT = tic;
        T = D.(state.tag);
        cla(axTau);
        stp = max(1, floor(height(T) / 500));      % 抽稀：曲线不必每点都画
        plot(axTau, T.t_s(1:stp:end), T{1:stp:end, tcol}, 'LineWidth', 0.8);
        hold(axTau, 'on');
        yline(axTau,  3.6, 'r--', 'peak 3.6',  'LineWidth', 1.1);
        yline(axTau, -3.6, 'r--', 'LineWidth', 1.1);
        yline(axTau,  0.6, 'b:',  'rated 0.6', 'LineWidth', 1.0);
        yline(axTau, -0.6, 'b:',  'LineWidth', 1.0);
        hold(axTau, 'off');
        ylabel(axTau, 'joint torque (N\cdotm)'); xlabel(axTau, 't (s)');
        grid(axTau, 'on'); title(axTau, files{v, 2}, 'FontSize', 10);
        legend(axTau, {'15 joints (inverse dynamics)', 'peak 3.6 N\cdotm', '', ...
            'rated 0.6 N\cdotm'}, 'Location', 'northeast', 'FontSize', 8);
        hLine = xline(axTau, 0, 'k-', 'LineWidth', 1.2);
        render(T);
    end

    function render(T)
        i = state.idx;
        q = poseAt(T, i);
        bx = T.base_x(i); by = T.base_y(i); bz = T.base_z(i);

        if strcmp(state.mode, 'skel')
            if ishghandle(state.hgPrev), delete(state.hgPrev); state.hgPrev = []; end
            if ~state.groundDrawn, drawGround(); state.groundDrawn = true; end
            setSkelVisible(true);
            drawSkeleton(q, bx, by, bz);
        else
            setSkelVisible(false);
            if ishghandle(state.hgPrev), delete(state.hgPrev); state.hgPrev = []; end
            % ⚠️ show(...) 会清空整个 axes（连地面一起），所以地面要随后重建
            show(robot, q, 'Parent', ax3d, 'PreservePlot', false, 'Frames', 'off');
            hg = hgtransform('Parent', ax3d);
            ch = ax3d.Children;
            set(ch(ch ~= hg), 'Parent', hg);
            hg.Matrix = makehgtform('translate', [bx, by, bz]);
            state.hgPrev = hg;
            state.groundDrawn = false;
            drawGround();
            state.groundDrawn = true;
        end

        xlim(ax3d, [bx-0.22 bx+0.22]); ylim(ax3d, [-0.17 0.17]); zlim(ax3d, [-0.02 0.36]);
        view(ax3d, 35, 18);
        title(ax3d, sprintf('x = %.3f m   t = %.2f s', bx, T.t_s(i)), 'FontSize', 10);

        if mod(state.nframe, 4) == 1
            if exist('hLine', 'var') && ~isempty(hLine) && isvalid(hLine)
                set(hLine, 'Value', T.t_s(i));
            end
            set(sld, 'Value', i / height(T));
            advStr = 'real-time'; if state.adv > 0, advStr = sprintf('%d frames', state.adv); end
            set(txtInfo, 'String', sprintf(['t = %7.2f s / %.0f s    x = %6.3f m    ' ...
                'advance = %s    ~%.1f fps    (kinematic replay, no physics / 仅运动学回放)'], ...
                T.t_s(i), T.t_s(end), bx, advStr, state.fps));
            cla(axTab);
            cfgDeg = rad2deg(T{i, qcol});
            vals = T{i, tcol};
            txt = cell(numel(JN) + 1, 1);
            txt{1} = sprintf('%-18s %9s %9s', 'joint', 'deg', 'N·m');
            for k = 1:numel(JN)
                txt{k+1} = sprintf('%-18s %9.2f %9.3f', JN(k), cfgDeg(k), vals(k));
            end
            text(axTab, 0, 0.98, txt, 'VerticalAlignment', 'top', ...
                'FontName', 'Consolas', 'FontSize', 7);   % 16 行要放得下，字号 8 会被滑块压住
        end
    end

    function drawGround()
        hold(ax3d, 'on');
        patch(ax3d, [-1 1.5 1.5 -1], [-0.22 -0.22 0.22 0.22], [0 0 0 0], ...
            'FaceColor', [0.94 0.94 0.94], 'EdgeColor', 'none', 'Tag', 'ground');
        gx = (-0.6:0.02:0.6)';        % 每 2 cm 一条 = 一个步态周期的前进量
        X = [gx, gx, nan(size(gx))]';
        Y = repmat([-0.20, 0.20, nan], numel(gx), 1)';
        Z = repmat([0.0005, 0.0005, nan], numel(gx), 1)';
        plot3(ax3d, X(:), Y(:), Z(:), 'Color', [0.72 0.72 0.72], 'Tag', 'ground');
        hold(ax3d, 'off');
    end

    function setSkelVisible(tf)
        if ~tf
            if ~isempty(state.hSkel)
                h = state.hSkel;
                try, delete([h.seg, h.jnt, h.soleL, h.soleR, h.body]); catch, end
                state.hSkel = [];
            end
            return
        end
        if isempty(state.hSkel)
            hold(ax3d, 'on');
            h.seg = plot3(ax3d, nan(1, 2*nseg), nan(1, 2*nseg), nan(1, 2*nseg), ...
                '-', 'Color', [0.15 0.15 0.18], 'LineWidth', 1.6, 'Tag', 'skel');
            h.jnt = plot3(ax3d, nan(1, nseg), nan(1, nseg), nan(1, nseg), ...
                'o', 'MarkerSize', 3, 'MarkerFaceColor', [0.85 0.25 0.20], ...
                'MarkerEdgeColor', 'none', 'Tag', 'skel');
            h.soleL = patch(ax3d, 'Vertices', nan(8,3), 'Faces', SOLE_FACES, ...
                'FaceColor', [0.30 0.45 0.85], 'FaceAlpha', 0.85, 'EdgeColor', 'none', 'Tag', 'skel');
            h.soleR = patch(ax3d, 'Vertices', nan(8,3), 'Faces', SOLE_FACES, ...
                'FaceColor', [0.85 0.45 0.20], 'FaceAlpha', 0.85, 'EdgeColor', 'none', 'Tag', 'skel');
            h.body = patch(ax3d, 'Vertices', nan(8,3), 'Faces', SOLE_FACES, ...
                'FaceColor', [0.35 0.35 0.38], 'FaceAlpha', 0.9, 'EdgeColor', 'none', 'Tag', 'skel');
            hold(ax3d, 'off');
            state.hSkel = h;
        end
    end

    function drawSkeleton(q, bx, by, bz)
        Tw = zeros(4, 4, numel(skelBodies));
        for k = 1:numel(skelBodies)
            Tw(:, :, k) = getTransform(robot, q, skelBodies{k});
        end
        off = [bx; by; bz];
        seg = nan(3, 2*nseg);
        n = 0;
        for k = 1:numel(skelBodies)
            p = Tw(1:3, 4, k) + off;
            n = n + 1; seg(:, 2*n-1) = p;
            ip = find(strcmp(skelBodies, skelParent{k}), 1);
            if isempty(ip), seg(:, 2*n) = off; else, seg(:, 2*n) = Tw(1:3, 4, ip) + off; end
        end
        set(state.hSkel.seg, 'XData', seg(1,:), 'YData', seg(2,:), 'ZData', seg(3,:));
        jp = reshape(Tw(1:3, 4, :), 3, []) + off;
        set(state.hSkel.jnt, 'XData', jp(1,:), 'YData', jp(2,:), 'ZData', jp(3,:));
        if iAnkL > 0
            set(state.hSkel.soleL, 'Vertices', boxVerts(Tw(:,:,iAnkL), SOLE_C(L,:), SOLE_H, off));
        end
        if iAnkR > 0
            set(state.hSkel.soleR, 'Vertices', boxVerts(Tw(:,:,iAnkR), SOLE_C(R,:), SOLE_H, off));
        end
        if iBase > 0
            set(state.hSkel.body, 'Vertices', ...
                boxVerts(Tw(:,:,iBase), [0 0 0.014], [0.075 0.050 0.030], off));
        end
    end

    function shutdown()
        try
            if isa(tmr, 'timer') && isvalid(tmr), stop(tmr); delete(tmr); end
        catch
        end
        if isvalid(fig), delete(fig); end
    end
end

% ================= 局部函数 / local functions =================

function q = local_pose(robot, q0, JN, qcol, T, i)
% 从数据行构造配置向量。⚠️ q_* 是**弧度**，不做任何换算。
q = q0;
vals = table2array(T(i, cellstr(qcol)));
for k = 1:numel(JN)
    idx = 0;
    for b = 1:robot.NumBodies
        if strcmp(robot.Bodies{b}.Joint.Name, char(JN(k))), idx = b - 1; break; end
    end
    if idx > 0, q(idx) = vals(k); end
end
end

function n = checkLimits(robot, q)
% 关节角是否越出 URDF 限位（单位错会立刻暴露）
n = 0;
for b = 2:robot.NumBodies
    j = robot.Bodies{b}.Joint;
    if ~strcmp(j.Type, 'revolute'), continue; end
    lim = j.PositionLimits;
    if isempty(lim) || numel(lim) < 2, continue; end
    if q(b-1) < lim(1) - 1e-6 || q(b-1) > lim(2) + 1e-6, n = n + 1; end
end
end

function z = soleLowestZ(robot, q, link, baseZ)
% 脚掌碰撞盒四个底角在世界系的**最低**高度（用 URDF 正运动学，与 MuJoCo 侧一致）
% ⚠️ 必须同时用上踝连杆的**旋转与平移**：只取旋转会漏掉整条腿的长度，
% 算出来的"脚底高度"其实是"脚掌相对踝关节的偏移"（第一版就这么错了，
% 自检报 +134 mm 才发现）。
T = getTransform(robot, q, link);
R = T(1:3, 1:3);
t = T(1:3, 4);
switch link
    case 'left_ankle_link',  c = [0,  0.0216, -0.0288];
    otherwise,               c = [0, -0.0216, -0.0288];
end
h = [0.0402, 0.0256, 0.0057];
z = inf;
for sx = [-1 1]
    for sy = [-1 1]
        p = t + R * (c(:) + [sx*h(1); sy*h(2); -h(3)]);
        z = min(z, p(3) + baseZ);
    end
end
end

function V = boxVerts(Tw, c, h, off)
s = [-1 -1 -1; 1 -1 -1; 1 1 -1; -1 1 -1; -1 -1 1; 1 -1 1; 1 1 1; -1 1 1];
V = (c + s .* h) * Tw(1:3, 1:3).' + (Tw(1:3, 4) + off).';
end
