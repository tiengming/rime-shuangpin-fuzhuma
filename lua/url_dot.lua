-- 智能点号：中文模式下在英文/网址上下文里把 '.' 输出为半角，其余情况仍是「。」
--
-- 判定规则（全部条件满足时才接管，否则返回 kNoop 交给 punctuator，行为与原来完全一致）：
--   1. 未组字，且上一次上屏以英文字母 / 数字 / 半角点结尾   -> 上屏 "."
--   2. 正在组字，输入串是纯英文数字等拉丁字符，且没有任何中文候选，
--      并且输入串长度 >= 2                                  -> 原文上屏输入串，再上屏 "."
--   3. 正在组字，上一次上屏以半角点结尾（同一个网址的续写）   -> 原文上屏输入串，再上屏 "."
--
-- 安全措施：整个处理过程包在 pcall 里，任何异常都退回 kNoop；
-- 组字中只要已经存在标点片段（含数字后的半选小数点）就一律不接管。
-- 关闭方法：删除 schema 里 engine/processors 下的 "lua_processor@*url_dot" 一行。

local M = {}

local kNoop = 2
local kAccepted = 1

-- 上次上屏的结尾是英文字母 / 数字 / 半角点
local function ends_with_latin(s)
    if not s or s == '' then
        return false
    end
    local b = s:byte(-1)
    if not b then
        return false
    end
    return (b >= 0x30 and b <= 0x39)  -- 0-9
        or (b >= 0x41 and b <= 0x5a)  -- A-Z
        or (b >= 0x61 and b <= 0x7a)  -- a-z
        or b == 0x2e                  -- .
end

local function is_ascii(s)
    if not s then
        return false
    end
    for i = 1, #s do
        if s:byte(i) > 0x7f then
            return false
        end
    end
    return true
end

-- 组字中是否已经有候选是中文（出错时按“有中文”处理，宁可不动）
local function has_cjk_candidate(ctx)
    local ok, res = pcall(function()
        local comp = ctx.composition
        if not comp then
            return false
        end
        local segs = comp:get_segments()
        if not segs then
            return false
        end
        for _, seg in ipairs(segs) do
            local menu = seg.menu
            if menu then
                menu:prepare(6)
                local n = menu:candidate_count()
                for i = 0, n - 1 do
                    local cand = menu:get_candidate_at(i)
                    if cand and cand.text and not is_ascii(cand.text) then
                        return true
                    end
                end
            end
        end
        return false
    end)
    if ok then
        return res
    end
    return true
end

-- 组字里所有片段都还没有被选中/确认（没有用户已经点过的候选），出错时按“有”处理
local function nothing_selected(ctx)
    local ok, res = pcall(function()
        local comp = ctx.composition
        if not comp then
            return true
        end
        local segs = comp:get_segments()
        if not segs then
            return true
        end
        for _, seg in ipairs(segs) do
            local status = seg.status
            if status == 'kSelected' or status == 'kConfirmed' then
                return false
            end
        end
        return true
    end)
    if ok then
        return res
    end
    return false
end

-- 组字中是否已经存在标点片段（含数字后半选的小数点），出错时同样按“有”处理
local function has_punct_segment(ctx)
    local ok, res = pcall(function()
        local comp = ctx.composition
        if not comp then
            return false
        end
        local segs = comp:get_segments()
        if not segs then
            return false
        end
        for _, seg in ipairs(segs) do
            if seg:has_tag('punct') or seg:has_tag('punct_number') then
                return true
            end
        end
        return false
    end)
    if ok then
        return res
    end
    return true
end

local function process(key, env)
    -- 只处理点号本身
    if key.keycode ~= 0x2e then
        return kNoop
    end
    if key:release() or key:ctrl() or key:alt() or key:super() then
        return kNoop
    end

    local ctx = env.engine.context
    -- 已经切到半角标点 / 英文模式时，交给原有流程
    if ctx:get_option('ascii_punct') or ctx:get_option('ascii_mode') then
        return kNoop
    end

    local last = ''
    local history = ctx.commit_history
    if history then
        local record = history:back()
        if record and record.text then
            last = record.text
        end
    end

    local input = ctx.input or ''

    -- 情况 1：没有组字，看上一次上屏的内容
    if input == '' then
        if ends_with_latin(last) then
            env.engine:commit_text('.')
            return kAccepted
        end
        return kNoop
    end

    -- 情况 2 / 3：组字中，只接管纯拉丁串
    if #input < 2 or #input > 64 then
        return kNoop
    end
    if not input:match('^[%a%d%-_~/:%?&=%%%.]+$') then
        return kNoop
    end
    if has_punct_segment(ctx) then
        return kNoop
    end

    local continues_url = last:sub(-1) == '.'
    if not continues_url and has_cjk_candidate(ctx) then
        return kNoop
    end

    -- 组字里已经有用户选过的候选时不动它，避免吞掉已经确认的内容
    if not nothing_selected(ctx) then
        return kNoop
    end

    -- 清空组字（原文按当前输入串上屏），再补一个半角点
    local raw = input
    ctx.input = ''
    env.engine:commit_text(raw .. '.')
    return kAccepted
end

function M.func(key, env)
    local ok, ret = pcall(process, key, env)
    if ok and ret then
        return ret
    end
    return kNoop
end

return M
