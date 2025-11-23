local socket = nil
local udp = nil
local log_file = nil
local lfs = require("lfs")
local previous_total = 0

package.path = package.path .. ";.\\LuaSocket\\?.lua"
package.cpath = package.cpath .. ";.\\LuaSocket\\?.dll"

-- 日志记录函数
function log_status(msg)
    if log_file then
        log_file:write(os.date("[%Y-%m-%d %H:%M:%S] ") .. msg .. "\n")
        log_file:flush()
    end
end

-- 1. 创建UDP socket
function LuaExportStart()
    -- 初始化日志文件
    log_file = io.open(lfs.writedir() .. "/Logs/sockettest1.log", "w")
    if not log_file then return end

    --加载python后台程序
    local exe_path = lfs.writedir() .. "Scripts/main.exe"  -- 确保路径正确
    local command = string.format('start "" "%s"', exe_path)
    local success, err = pcall(os.execute, command)
    if success then
        log_status("成功启动main.exe: " .. exe_path)
    else
        log_status("启动失败: " .. tostring(err))
    end

    -- 加载LuaSocket
    local success, err = pcall(function()
        socket = require("socket")
        log_status("LuaSocket加载成功, 版本: ".. socket._VERSION)
        
        -- 创建UDP socket并设置目标地址
        local host = "127.0.0.1"
        local port = 50050
        udp = socket.udp()
        udp:setpeername(host, port)
        udp:settimeout(0) -- 非阻塞模式
        log_status("UDP已初始化，目标地址: "..host..":"..port)
    end)
    
    if not success then
        log_status("UDP初始化失败: "..tostring(err))
    end
end

-- 获取引擎相关数据
function GetEngineData()
    local engineInfo = LoGetEngineInfo()
    if engineInfo then
        -- 读取左右引擎 RPM（百分比格式）
        local rpmLeft = engineInfo.RPM.left and engineInfo.RPM.left or 0
        local rpmRight = engineInfo.RPM.right and engineInfo.RPM.right or 0
        return rpmLeft,rpmRight
    end
end

-- 获取左右引擎加力燃烧室状态（0.0-1.0）
function GetAfterburnerStatus()
    local abLeft = LoGetAircraftDrawArgumentValue(28) or 0  -- 左引擎加力参数
    local abRight = LoGetAircraftDrawArgumentValue(29) or 0 -- 右引擎加力参数
    return abLeft, abRight
end

-- 获取飞机油耗
function GetFuelConsumption()
    local engineInfo = LoGetEngineInfo()
    if engineInfo then
        -- 读取左右引擎燃油消耗量（kg/s）
        local fuelLeft = engineInfo.FuelConsumption and engineInfo.FuelConsumption.left or 0
        local fuelRight = engineInfo.FuelConsumption and engineInfo.FuelConsumption.right or 0
        return fuelLeft + fuelRight
    end
    return 0
end

-- 获取当前总油量
function GetTotalFuel()
    local engineInfo = LoGetEngineInfo()
    if engineInfo then
        -- 内部油箱 + 外部油箱（单位：千克）
        local internal = engineInfo.fuel_internal or 0
        local external = engineInfo.fuel_external or 0
        return internal + external
    end
    return 0
end

-- 获取飞机引擎温度
function GetEngineTemperature()
    local engineInfo = LoGetEngineInfo()
    if engineInfo and engineInfo.Temperature then
        -- 读取左右引擎温度（摄氏度）
        local tempLeft = engineInfo.Temperature.left or 0
        local tempRight = engineInfo.Temperature.right or 0
        return tempLeft + tempRight
    end
    return 0, 0
end

--获取飞机接地状态
function CheckGroundContact()
    local mechInfo = LoGetMechInfo()
    -- return mechInfo.gear.main.left.rod , mechInfo.gear.main.right.rod
    -- 检查是否存在有效的机械数据
    if mechInfo and mechInfo.gear and mechInfo.gear.main then
        local left_rod = mechInfo.gear.main.left.rod or 0
        local right_rod = mechInfo.gear.main.right.rod or 0
        
        -- 如果左右主起落架液压杆均被压缩（触地）
        if left_rod > 0 or right_rod > 0 then
            return 1 -- 接地状态
        end
    end
    
    return 0 -- 未接地状态
end

--读取当前飞机名称
function GetAircraftName()
    local selfData = LoGetSelfData()
    local aircraft = selfData and selfData.Name or "UNKNOWN"
    return aircraft
end

-- 获取弹药相关数据
function GetAircraftArmo()
    -- 获取机炮弹药数据
    local ammo_count = 0
    local payloadInfo = LoGetPayloadInfo()
    if payloadInfo then
        ammo_count = payloadInfo.Cannon and payloadInfo.Cannon.shells or 0
        return ammo_count
    end
end

-- 获取挂载信息
function GetAircraftPayload()
    -- 初始化总弹药数
    local total_bomb = 0
    
    -- 获取挂载信息
    local payload_info = LoGetPayloadInfo()
    
    if payload_info and payload_info.Stations then
        -- 遍历所有挂载点计算总数
        for _, station in pairs(payload_info.Stations) do
            total_bomb = total_bomb + station.count
        end
    end
    
    return total_bomb
end

-- 新增获取减速板状态的函数
function GetSpeedBrakeStatus()
    local mechInfo = LoGetMechInfo()
    if mechInfo and mechInfo.speedbrakes then
        -- status: 0=收起, 1=展开中, 2=收拢中, 3=完全展开
        -- value: 展开程度 (0.0-1.0)
        return mechInfo.speedbrakes.status, mechInfo.speedbrakes.value * 100
    end
    return 0, 0.0  -- 默认值
end

-- 获取飞机G力
function GetAircraftG()
    local accel = LoGetAccelerationUnits()
    if accel then
        local Gx = accel.x or 0
        local Gy = accel.y or 0
        local Gz = accel.z or 1
        local totalG = math.sqrt(Gx^2 + Gy^2 + (Gz-1)^2)
        return totalG
    else
        -- 无法获取数据时返回默认值（如 1G 或 0）
        return 1.0  -- 或 return 0
    end
end

-- 获取飞机真空速
function GetTAS()
    local TAS = LoGetTrueAirSpeed()
    if TAS then
        return TAS*1.94384
    else
        return 1
    end
end

-- 获取干扰弹总数量
function GetCountermeasures()
    local snares = LoGetSnares()
    if snares and type(snares) == "table" then
        -- 官方明确说明返回格式为 {chaff数量, flare数量}
        local chaff = snares.chaff or 0
        local flare = snares.flare or 0
        return chaff + flare  
    else
        -- 游戏未运行或接口异常时返回0
        return 0
    end
end

-- 新增函数：获取RWR告警状态（0-正常，1-被锁定，2-导弹来袭）
function GetRWRStatus()
    local rwr_info = LoGetTWSInfo()
    local status = 0  -- 默认无告警
    
    if rwr_info and rwr_info.Emitters then
        for _, emitter in pairs(rwr_info.Emitters) do
            -- 检查信号类型
            if emitter.SignalType == "missile_radio_guided" then
                status = 2  -- 最高优先级，直接返回导弹警告
                return status
            elseif emitter.SignalType == "lock" then
                status = 1  -- 次级优先级，标记为锁定状态（可能后面还有导弹警告）
            end
        end
    end
    
    return status
end

-- 发送飞机数据
-- 核心数据发送逻辑（从LuaExportAfterNextFrame迁移至此）
function SendAircraftData(t)
    if udp then
        -- 获取数据（保持原有逻辑）
        local current_time = LoGetModelTime()
        local current_ammo = GetAircraftArmo()
        local current_name = GetAircraftName()
        local current_G = GetAircraftG()
        local total_bomb = GetAircraftPayload()
        local brake_status, brake_value = GetSpeedBrakeStatus()
        local OnGround = CheckGroundContact()
        local AB_L, AB_R = GetAfterburnerStatus()
        local current_TAS = GetTAS()
        local current_counter = GetCountermeasures()
        local rwr_status = GetRWRStatus()

        -- 序列化数据
        local payload = string.format(
            "TIME=%.2f, NAME=%s, AMMO=%d, COUNTER=%d, RWR=%d, AB_L=%.2f, AB_R=%.2f, G=%.2f, SpeedBrake=%.2f, OnGround=%d, total_bomb=%d, TAS=%d",
            current_time,
            current_name,
            current_ammo,
            current_counter,
            rwr_status,
            AB_L,
            AB_R,
            current_G,
            brake_value,
            OnGround,
            total_bomb,
            current_TAS
        )
    
        -- 通过UDP发送
        local success, err = pcall(function()
            udp:send(payload)
            log_status("发送成功: "..payload)
        end)
        
        if not success then
            log_status("发送失败: "..tostring(err))
        end
    end
end

-- 定时任务调度（新增）
function LuaExportActivityNextEvent(t)
    local tNext = t + 0.1  -- 设置0.1秒间隔
    
    if LoGetSelfData() then
        -- 执行数据发送
        SendAircraftData(t)
    else
        log_status("Player not in aircraft, skipping data send.")
    end
    
    return tNext  -- 返回下次触发时间
end

-- 关闭连接
function LuaExportStop()
    if udp then
        udp:close()
        log_status("UDP连接已关闭")
    end
    if log_file then
        log_file:close()
        log_file = nil
    end

    --关闭后台python程序
    os.execute('taskkill /IM main.exe /F')  -- 强制终止进程
    log_status("已终止main.exe")
end

-- 空函数以满足导出要求
function LuaExportAfterNextFrame() end
function LuaExportBeforeNextFrame() end