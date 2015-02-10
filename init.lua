-- a mod for displaying Minetest maps
-- David Mckenzie 2014
-- License: WTFPL v2
--
-- updateInterval for automatic regeneration of maps can be changed on line 53 (updateInterval = x)

local mapitFormspecBasic = ""
local mapitFormspecTP = ""
local mapitFormspecMouse = ""
local mapitPlayerName = ""
local mapitMapState = ""
local mapitwFormFu = 0

local curLine = 0
local mapitMapState = ""
local butX=0
local butZ=0
local worldStepWuX = 0
local worldStepWuZ = 0
local pngMinWuX = 0
local pngMaxWuZ = 0

local inv_mod = nil

function file_exists(name)
   local f=io.open(name,"r")
   if f~=nil then io.close(f) return true else return false end
end

function file_copy(source, target)
	local infile = io.open(source, "r")
	local instr = infile:read("*a")
	infile:close()

	local outfile = io.open(target, "w")
	outfile:write(instr)
	outfile:close()
end

local updateMap = function(forceUpdate)
	if forceUpdate == nil then forceUpdate = false end

	-- GET NAMES AND PATHS TO ENSURE CORRECT MAP IS USED
	local worldPath = minetest.get_worldpath()
	local worldName = string.gsub(worldPath, "(.*/)(.*)", "%2")
	local worldsqlName = worldPath.. "/map.sqlite"
	if not file_exists(worldsqlName) then return 0 end

	local curModPath = minetest.get_modpath('mapit')
	local texPath = curModPath.. "/textures/"
	local dummyFilePName = texPath.. "mapit.png"
	local mapFileName = worldName:gsub("%s+", "_").. ".png"
	local thumbFileName = worldName:gsub("%s+", "_").. "_thumb.png"
	local mapFilePName = texPath.. mapFileName
	local thumbFilePName = texPath.. thumbFileName
	local mapitHistoryPName = texPath.. "mapitHistory.txt"


	--this should never be required
	--os.execute("mkdir \"" .. texPath "\"") --create directory if it does not already exist

	-- if there's a failure of the python script, at least there'll be a dummy file
	if not file_exists(mapFilePName) then file_copy(dummyFilePName, mapFilePName) end
	if not file_exists(thumbFilePName) then file_copy(dummyFilePName, thumbFilePName) end

	local updateInterval = 7*24*60*60		-- number of seconds between updates

	-- update the history to save the generation date
	local lastUpdateTime = 0
	local fh = io.open(mapitHistoryPName, "r")
	local fileStr = ""
	while true do
        	curLine = fh.read(fh)
        	if not curLine then break end
		local cWN, lUT = curLine:match("(%w+)%s=%s(%d+)")
--		if cWN == nil then cWN = ""
--		if lUT == nil then lUT = 0
--		print(cWN)
--		print(lUT)
		if cWN == (worldName) then
			lastUpdateTime = tonumber(lUT)
		else
			fileStr = fileStr.. curLine
		end		
--        	print (line)
        end

	-- get last modified time direct from the file
	--for this to work, you will need to have installed luaFileSystem
	--sudo luarocks install luafilesystem
	--sudo apt-get install luarocks
--	local lfsExists, lfs = pcall(function () require "lfs" end)
	local lfsExists, lfs = pcall(require, "lfs")
	if lfsExists then
--	local lfs = require "lfs"
		local lastUpdateTime = lfs.attributes( mapFilePName ).modification
	end
	
	if (lastUpdateTime < os.time()-updateInterval) or forceUpdate then
		fileStr = fileStr.. worldName.. " = ".. os.time().. "\r\n"
		fh:close()

		-- run the python script to generate the map (could be run in background by appending an '&' to the string, but texture might be corrupted or out of date for current load)
		local osx = "python \"".. curModPath.. "/".. "minetestmapper-numpy.py\" --pixelspernode 1 --drawscale \"".. worldPath.. "\" \"".. mapFilePName.. "\""
		os.execute(osx)
		print("mapit: Updated map for ".. worldName)
	
		fh = io.open(mapitHistoryPName, "w")
		fh:write(fileStr)
	else
		print("mapit: Map update not required for ".. worldName)
	end
	fh:close()
--	print (fileStr)
	return
end

updateMap()

minetest.register_node('mapit:mapblock', {
        -- ideally would have an automatic way of creating a face for the block which was correctly dimensions and aspect ratio
        -- currently using a large .png introduces sig delay due to time drawing the faces
	description = "Map Block",
	tiles = { string.gsub(string.gsub(minetest.get_worldpath(), "(.*/)(.*)", "%2"),"%s+", "_").."_thumb.png",
		  string.gsub(string.gsub(minetest.get_worldpath(), "(.*/)(.*)", "%2"),"%s+", "_").."_thumb.png",
		  string.gsub(string.gsub(minetest.get_worldpath(), "(.*/)(.*)", "%2"),"%s+", "_").."_thumb.png",
		  string.gsub(string.gsub(minetest.get_worldpath(), "(.*/)(.*)", "%2"),"%s+", "_").."_thumb.png",
		  string.gsub(string.gsub(minetest.get_worldpath(), "(.*/)(.*)", "%2"),"%s+", "_").."_thumb.png",
		  string.gsub(string.gsub(minetest.get_worldpath(), "(.*/)(.*)", "%2"),"%s+", "_").."_thumb.png",
	},
	sunlight_propagates = false,
	paramtype = "light",
	walkable = true,
	groups = {cracky=3},
})


minetest.register_node('mapit:teleportWaypoint', {
	description = "Teleport Point",
	drawtype = "plantlike",
	inventory_image = "apophysisFlame.png",
	wield_image = "apophysisFlame.png",
	tiles = { "apophysisFlame.png" },
	sunlight_propagates = false,
	paramtype = "light",
	walkable = true,
--	sounds = default.node_sound_leaves_defaults(),
	groups = {cracky=3},
})


minetest.register_tool("mapit:maptool", {
	description = "Map Tool",
	inventory_image = string.gsub(string.gsub(minetest.get_worldpath(), "(.*/)(.*)", "%2"),"%s+", "_")..".png",
	on_use = function(itemstack, user, pointed_thing)
	map_handler_maptool(itemstack,user,pointed_thing)
	end,
})
function map_handler_maptool (itemstack, user, pointed_thing)
	mapitPlayerName=user:get_player_name()
	generateMapStrings(mapitPlayerName)
	minetest.show_formspec(mapitPlayerName, "mapit:maptool", mapitFormspecBasic)
end

function generateMapStrings()
	-- suffixes: Fu = form units; Wu = world units; Pp = porportion; Px = pixels
	print(name)

	local player = minetest.get_player_by_name(mapitPlayerName)
	print(mapitPlayerName)
	print(player)


	local posWu = player:getpos()
	local map
	local yaw
	local rotate = 0
	local facing = "Not set"	-- direction player is facing (NSEW)
	local wFormFu
	local hFormFu
	local width, height

--	globals
	mapitMapState = ""
	butX=-1
	butZ=-1
	local wPNGPx, hPNGPx, pngRegionWu, borderPx, pixPerNodePx


	--		posWu.y = posWu.y + 1
        yaw = player:get_look_yaw()
        if yaw ~= nil then
		-- Find angle player facing to enable rotation of position arrow based on yaw.
		yaw = math.deg(yaw)
		yaw = math.fmod (yaw, 360)
		if yaw<0 then yaw = 360 + yaw end
		if yaw>360 then yaw = yaw - 360 end           
		if yaw < 90 then
			rotate = 90
		elseif yaw < 180 then
			rotate = 180
		elseif yaw < 270 then
			rotate = 270
		else
			rotate = 0
		end
		if yaw>315 or yaw<=45 then
			facing="East"
		elseif yaw>45 and yaw<=135 then
			facing="South"
		elseif yaw>135 and yaw<=225 then
			facing="West"
		elseif yaw>225 and yaw<=315 then
			facing="North"
		end

		yaw = math.fmod(yaw, 90)
		yaw = math.floor(yaw / 10) * 10
        end

-- Bizarrely yaw seems to vary with world, so direction is incorrect (and the pos values are listed anyway so unnecessary).
--	minetest.chat_send_player(mapitPlayerName, "mapit: Current Loc: X: ".. math.floor(posWu.x).. ", Y:".. math.floor(posWu.y).. ", Z:".. math.floor(posWu.z).. ", Facing:"..   facing, false)


	-- GET NAMES AND PATHS TO ENSURE CORRECT MAP IS USED
	local worldPath = minetest.get_worldpath()
	local worldName = string.gsub(worldPath, "(.*/)(.*)", "%2")

	local curModPath = minetest.get_modpath('mapit')
	local mapFileName = curModPath.. "/textures/".. worldName:gsub("%s+", "_").. ".png"

	-- PARSE THE PNG TO EXTRACT MAP LOCATIONS
	wPNGPx, hPNGPx, pngRegionWu, pngMinWuX, pngMaxWuZ, borderPx, pixPerNodePx = parse_png (mapFileName)


	-- CALCULATE WORLD AND FORM DIMENSIONS AND PROPORTIONS
	local wWorldWu=(wPNGPx-borderPx)/pixPerNodePx
	local hWorldWu=(hPNGPx-borderPx)/pixPerNodePx
	local wWorldUnitPp= pixPerNodePx/wPNGPx
	local hWorldUnitPp= pixPerNodePx/hPNGPx
	local lBorderPp = borderPx/(wPNGPx-borderPx)
	local tBorderPp = borderPx/(hPNGPx-borderPx)

	-- determine required form width to maintain PNG aspect ratio (known z/height)
	local aspectRatio = wPNGPx/hPNGPx
--	print(aspectRatio)
	if aspectRatio > 1.35 then
		wFormFu = 16
		hFormFu = (wFormFu-1)/aspectRatio
	else
		hFormFu = 11	-- height of the form
		wFormFu = hFormFu*aspectRatio +1
	end
	local wMapFu = hFormFu*aspectRatio
	local hMapFu = hFormFu
	local lBorderFu =wMapFu * lBorderPp
	local tBorderFu = hMapFu * tBorderPp

	
	-- SCALE AND LOCATE ARROW
	local arrowSizeFuZ=0.4
	local arrowSizeFuX=0.4		--*aspectRatio
	-- Distance from world location at PNG origin to player current location (in WORLD UNITS)
	local pngOriginToPlayerWuX = posWu.x - pngMinWuX	-- x axis is more POSITIVE away from origin
	local pngOriginToPlayerWuZ = pngMaxWuZ - posWu.z	-- z axis is more NEGATIVE away from origin
	-- Distance from world location at PNG origin to player current location (in PIXELS)
	local playerLocFuX = wMapFu*pngOriginToPlayerWuX*wWorldUnitPp	-- location for middle of arrow icon (in pixels)
	local playerLocFuZ = hMapFu*pngOriginToPlayerWuZ*hWorldUnitPp	-- location for middle of arrow icon (in pixels)
	-- location of arrow (in form units)
	local ArrowLocFuX = playerLocFuX + lBorderFu - arrowSizeFuX/2
	local ArrowLocFuZ = playerLocFuZ + tBorderFu
	-- generate the appropriate string for the arrow (to ensure rotation is correct)
        local imstr
	if rotate ~= 0 then
		imstr = "image["..ArrowLocFuX..","..ArrowLocFuZ..";"..arrowSizeFuX..","..arrowSizeFuZ..";d" .. yaw .. ".png^[transformFYR".. rotate .."]"
	else
		imstr = "image["..ArrowLocFuX..","..ArrowLocFuZ..";"..arrowSizeFuX..","..arrowSizeFuZ..";d" .. yaw .. ".png^[transformFY]"
	end

--		button[X,Y;W,H;name;label]
	local buttons = ""
	buttons = buttons.."button["..(wFormFu-0.8)..",0;0.8,0.8;zoomIn;z+]"
	buttons = buttons.."button["..(wFormFu-0.8)..",1;0.8,0.8;zoomOut;z-]"
	buttons = buttons.."button["..(wFormFu-0.8)..",2;0.8,0.8;updateMap;reMap]"
	buttons = buttons.."image_button["..(wFormFu-0.8)..",3;0.8,0.8;logo.png;teleport;T]"
	if minetest.get_modpath("travelpoints") then
		buttons = buttons.."image_button["..(wFormFu-0.8)..",4;0.8,0.8;teleport.png;TP;TP]"
	end

	local mapMouseButtons = ""
	worldStepWuX = wWorldWu/10
	worldStepWuZ = hWorldWu/10

	-- CREATE LIST OF BUTTONS TO OVERLAY MAP (FOR MOUSE CLICKS)
	for iy = 0,9 do
		for ix = 0,9 do
			mapMouseButtons = mapMouseButtons.."image_button["..((wMapFu-lBorderFu)/10*ix+lBorderFu)..","..((hMapFu-tBorderFu)/10*iy+tBorderFu)..";"..((wMapFu-lBorderFu)/8)..","..((hMapFu-tBorderFu)/8)..";blank.png;map"..ix..iy..";;true;false]"
--"..true..";"..true.."]"
		end
	end

--	print(minetest.get_modpath("mapit"))
--	print(minetest.get_modpath("travelpoints"))
	if minetest.get_modpath("travelpoints") then
		-- CREATE LIST OF TRAVELPOINT LOCATIONS TO OVERLAY ON MAP

		-- This code largely taken from travelpoints functions.lua
		-- Get travelpoints_array.
		local travelpoints_table = travelpoints.get_travelpoints_table(mapitPlayerName)
		local travelpoints_array = travelpoints.get_travelpoints_array(mapitPlayerName)
--		print(dump(travelpoints_array))
--		print("+++")
--		print(dump(travelpoints_table))

		-- Get travelpoint count.
		local tp_count = #travelpoints_array - 1
		local mapitTPButtons = ""
		-- Check if player has any travelpoints.
		if tp_count > 0 then
			-- Step through travelpoints_array.
			for index, value in ipairs(travelpoints_array) do
				-- Omit first index (used for travelpoints:transporter_pad/_active's formspec)
				if index > 1 and index <= 50 then
					-- Extract title from value: "<title> (<x>, <y>, <z>)"
					local title = string.match(value, "^([^ ]+)%s+")
					-- Output lines.
					-- <n>. <title> (<x>, <y>, <z>). Saved on <date> at <time>. Descripton: <desc>
					tPPos = travelpoints_table[title].pos

					-- SCALE AND LOCATE TRAVEL POINT
					local tPSizeFuZ=0.4
					local tPSizeFuX=0.4		--*aspectRatio
					-- Distance from world location at PNG origin to player current location (in WORLD UNITS)
					local pngOriginToTPWuX = travelpoints_table[title].pos.x - pngMinWuX	-- x axis is more POSITIVE away from origin
					local pngOriginToTPWuZ = pngMaxWuZ - travelpoints_table[title].pos.z	-- z axis is more NEGATIVE away from origin
					-- Distance from world location at PNG origin to player current location (in PIXELS)
					local tPLocFuX = wMapFu*pngOriginToTPWuX*wWorldUnitPp	-- location for middle of arrow icon (in pixels)
					local tPLocFuZ = hMapFu*pngOriginToTPWuZ*hWorldUnitPp	-- location for middle of arrow icon (in pixels)
					-- location of arrow (in form units)
					local tPLocFuX = tPLocFuX + lBorderFu - tPSizeFuX/2
					local tPLocFuZ = tPLocFuZ + tBorderFu
					-- generate the appropriate string for the travelpoint
					mapitTPButtons = mapitTPButtons.. "image_button[".. tPLocFuX.. ",".. tPLocFuZ.. ";".. tPSizeFuX.. ",".. tPSizeFuZ.. ";teleport.png;TP".. (index-2).. ";".. (index-2).. ";true;false]"
				
					mapitTPButtons = mapitTPButtons.. "button[".. wFormFu.. ",".. ((index-2)/2).. ";3,".. tPSizeFuZ.. ";TP".. (index-2).. ";".. (index-2).. " ".. title.. "]"
				elseif index > 50 then
					minetest.chat_send_player(mapitPlayerName, "Sorry: mapit can only fit 50 travelpoints on the map", false)
					break
				end
			end
		else
--			minetest.chat_send_player(mapitPlayerName, "You have no saved travelpoints.", false)
		end

		-- GENERATE THE STRING FOR TRAVELPOINTS FORM
		mapitwFormFu = wFormFu + 3
		mapitFormspecTP =  "size["..mapitwFormFu..","..hFormFu.."]"..
		                imstr..
	 			"background[0,0;"..wMapFu..","..hMapFu..";"..worldName:gsub("%s+", "_")..".png]"..
				buttons..
				mapitTPButtons
	end

	-- GENERATE THE FORM AND DISPLAY IT
        mapitFormspecBasic =  "size["..wFormFu..","..hFormFu.."]"..
                        imstr..
 			"background[0,0;"..wMapFu..","..hMapFu..";"..worldName:gsub("%s+", "_")..".png]"..
			buttons
--	print(mapitFormspecBasic)
	-- generate the string for the mousebuttons form
	mapitFormspecMouse = mapitFormspecBasic.. mapMouseButtons

print (mapitFormspecBasic)
	return mapitFormspecBasic
end


minetest.register_on_player_receive_fields(function(player, formname, fields)
	mapitPlayerName=player:get_player_name()

	butX=-1
--	print()
--	print("basic:".. mapitFormspecBasic)
--	print()
--	print("with multibutton:".. mapitFormspecMouse)
--	print()
--	print("--------")
--	print("map state:".. mapitMapState)


	if fields.uI then
		generateMapStrings()
		minetest.show_formspec(mapitPlayerName, "mapit:maptool", mapitFormspecBasic)
		mapitMapState = ""
	end
	if fields.zoomIn then
		minetest.chat_send_player(mapitPlayerName, "Zoom In not implemented", false)
		if mapitMapState == "+" then
			mapitMapState=""
			minetest.show_formspec(mapitPlayerName, "mapit:maptool", mapitFormspecBasic)
		else
			mapitMapState="+"
			minetest.show_formspec(mapitPlayerName, "mapit:maptool", mapitFormspecMouse)
		end
	end
	if fields.zoomOut then
		minetest.chat_send_player(mapitPlayerName, "Zoom Out not implemented", false)
		if mapitMapState == "-" then
			mapitMapState=""
			minetest.show_formspec(mapitPlayerName, "mapit:maptool", mapitFormspecBasic)
		else
			mapitMapState="-"
			minetest.show_formspec(mapitPlayerName, "mapit:maptool", mapitFormspecMouse)
		end
	end

	if fields.updateMap then
		minetest.chat_send_player(mapitPlayerName, "Updating Map, please be patient...", false)
		updateMap()
		minetest.chat_send_player(mapitPlayerName, "Map Updated. Please exit and re-enter world to reload the texture", false)
	end

	if fields.teleport then
		if mapitMapState == "t" then
			mapitMapState=""
			minetest.show_formspec(mapitPlayerName, "mapit:maptool", mapitFormspecBasic)
		else
			mapitMapState="t"
			minetest.show_formspec(mapitPlayerName, "mapit:maptool", mapitFormspecMouse)
		end
	end

	if minetest.get_modpath("travelpoints") then
		local travelpoints_table = travelpoints.get_travelpoints_table(mapitPlayerName)
		local travelpoints_array = travelpoints.get_travelpoints_array(mapitPlayerName)
		local tPIndex = -1

		if fields.TP then
			if mapitMapState == "tp" then
				mapitMapState=""
				minetest.show_formspec(mapitPlayerName, "mapit:maptool", mapitFormspecBasic)
			else
				-- Only display the form if there is at least one travelpoint
				local travelpoints_table = travelpoints.get_travelpoints_table(mapitPlayerName)
				local travelpoints_array = travelpoints.get_travelpoints_array(mapitPlayerName)
				local tp_count = #travelpoints_array - 1
				if tp_count > 0 then
					mapitMapState="tp"
					minetest.show_formspec(mapitPlayerName, "mapit:maptool", mapitFormspecTP)
				else
					minetest.chat_send_player(mapitPlayerName, "You have no saved travelpoints.", false)
				end
			end
		end
		if fields.TP0 then
			tPIndex = 2
		end
		if fields.TP1 then
			tPIndex = 3
		end
		if fields.TP2 then
			tPIndex = 4
		end
		if fields.TP3 then	
			tPIndex =5
		end	
		if fields.TP4 then	
			tPIndex =6
		end	
		if fields.TP5 then	
			tPIndex =7
		end	
		if fields.TP6 then	
			tPIndex =8
		end	
		if fields.TP7 then	
			tPIndex =9
		end	
		if fields.TP8 then	
			tPIndex =10
		end	
		if fields.TP9 then	
			tPIndex =11
		end	
		if fields.TP10 then	
			tPIndex =12
		end	
		if fields.TP11 then	
			tPIndex =13
		end	
		if fields.TP12 then	
			tPIndex =14
		end	
		if fields.TP13 then	
			tPIndex =15
		end	
		if fields.TP14 then	
			tPIndex =16
		end	
		if fields.TP15 then	
			tPIndex =17
		end	
		if fields.TP16 then	
			tPIndex =18
		end	
		if fields.TP17 then	
			tPIndex =19
		end	
		if fields.TP18 then	
			tPIndex =20
		end	
		if fields.TP19 then	
			tPIndex =21
		end	
		if fields.TP20 then	
			tPIndex =22
		end	
		if fields.TP21 then	
			tPIndex =23
		end	
		if fields.TP22 then	
			tPIndex =24
		end	
		if fields.TP23 then	
			tPIndex =25
		end	
		if fields.TP24 then	
			tPIndex =26
		end	
		if fields.TP25 then	
			tPIndex =27
		end	
		if fields.TP26 then	
			tPIndex =28
		end	
		if fields.TP27 then	
			tPIndex =29
		end	
		if fields.TP28 then	
			tPIndex =30
		end	
		if fields.TP29 then	
			tPIndex =31
		end	
		if fields.TP30 then	
			tPIndex =32
		end	
		if fields.TP31 then	
			tPIndex =33
		end	
		if fields.TP32 then	
			tPIndex =34
		end	
		if fields.TP33 then	
			tPIndex =35
		end	
		if fields.TP34 then	
			tPIndex =36
		end	
		if fields.TP35 then	
			tPIndex =37
		end	
		if fields.TP36 then	
			tPIndex =38
		end	
		if fields.TP37 then	
			tPIndex =39
		end	
		if fields.TP38 then	
			tPIndex =40
		end	
		if fields.TP39 then	
			tPIndex =41
		end	
		if fields.TP40 then	
			tPIndex =42
		end	
		if fields.TP41 then	
			tPIndex =43
		end	
		if fields.TP42 then	
			tPIndex =44
		end	
		if fields.TP43 then	
			tPIndex =45
		end	
		if fields.TP44 then	
			tPIndex =46
		end	
		if fields.TP45 then	
			tPIndex =47
		end	
		if fields.TP46 then	
			tPIndex =48
		end	
		if fields.TP47 then	
			tPIndex =49
		end	
		if fields.TP48 then	
			tPIndex =50
		end	
		if fields.TP49 then	
			tPIndex =51
		end	
		if fields.TP50 then	
			tPIndex =52
		end
	
		if tPIndex >=0 then
			for index, value in ipairs(travelpoints_array) do
				-- Omit first index (used for travelpoints:transporter_pad/_active's formspec)
				if index == tPIndex then
					-- Extract title from value: "<title> (<x>, <y>, <z>)"
					local title = string.match(value, "^([^ ]+)%s+")
					player:setpos(travelpoints_table[title].pos)
				end
			end
			generateMapStrings()
			minetest.show_formspec(mapitPlayerName, "mapit:maptool", mapitFormspecTP)
			mapitMapState = "tp"

		end
	end



	-- There seems to be no way to hook the mouse click directly, so make a 10x10 grid of transparent buttons and use these to approximate location
	if fields.map00 then
		butX=0
		butZ=0
	end
	if fields.map01 then
		butX=0
		butZ=1
	end
	if fields.map02 then
		butX=0
		butZ=2
	end
	if fields.map03 then
		butX=0
		butZ=3
	end
	if fields.map04 then
		butX=0
		butZ=4
	end
	if fields.map05 then
		butX=0
		butZ=5
	end
	if fields.map06 then
		butX=0
		butZ=6
	end
	if fields.map07 then
		butX=0
		butZ=7
	end
	if fields.map08 then
		butX=0
		butZ=8
	end
	if fields.map09 then
		butX=0
		butZ=9
	end
	if fields.map10 then
		butX=1
		butZ=0
	end
	if fields.map11 then
		butX=1
		butZ=1
	end
	if fields.map12 then
		butX=1
		butZ=2
	end
	if fields.map13 then
		butX=1
		butZ=3
	end
	if fields.map14 then
		butX=1
		butZ=4
	end
	if fields.map15 then
		butX=1
		butZ=5
	end
	if fields.map16 then
		butX=1
		butZ=6
	end
	if fields.map17 then
		butX=1
		butZ=7
	end
	if fields.map18 then
		butX=1
		butZ=8
	end
	if fields.map19 then
		butX=1
		butZ=9
	end
	if fields.map20 then
		butX=2
		butZ=0
	end
	if fields.map21 then
		butX=2
		butZ=1
	end
	if fields.map22 then
		butX=2
		butZ=2
	end
	if fields.map23 then
		butX=2
		butZ=3
	end
	if fields.map24 then
		butX=2
		butZ=4
	end
	if fields.map25 then
		butX=2
		butZ=5
	end
	if fields.map26 then
		butX=2
		butZ=6
	end
	if fields.map27 then
		butX=2
		butZ=7
	end
	if fields.map28 then
		butX=2
		butZ=8
	end
	if fields.map29 then
		butX=2
		butZ=9
	end
	if fields.map30 then
		butX=3
		butZ=0
	end
	if fields.map31 then
		butX=3
		butZ=1
	end
	if fields.map32 then
		butX=3
		butZ=2
	end
	if fields.map33 then
		butX=3
		butZ=3
	end
	if fields.map34 then
		butX=3
		butZ=4
	end
	if fields.map35 then
		butX=3
		butZ=5
	end
	if fields.map36 then
		butX=3
		butZ=6
	end
	if fields.map37 then
		butX=3
		butZ=7
	end
	if fields.map38 then
		butX=3
		butZ=8
	end
	if fields.map39 then
		butX=3
		butZ=9
	end
	if fields.map40 then
		butX=4
		butZ=0
	end
	if fields.map41 then
		butX=4
		butZ=1
	end
	if fields.map42 then
		butX=4
		butZ=2
	end
	if fields.map43 then
		butX=4
		butZ=3
	end
	if fields.map44 then
		butX=4
		butZ=4
	end
	if fields.map45 then
		butX=4
		butZ=5
	end
	if fields.map46 then
		butX=4
		butZ=6
	end
	if fields.map47 then
		butX=4
		butZ=7
	end
	if fields.map48 then
		butX=4
		butZ=8
	end
	if fields.map49 then
		butX=4
		butZ=9
	end
	if fields.map50 then
		butX=5
		butZ=0
	end
	if fields.map51 then
		butX=5
		butZ=1
	end
	if fields.map52 then
		butX=5
		butZ=2
	end
	if fields.map53 then
		butX=5
		butZ=3
	end
	if fields.map54 then
		butX=5
		butZ=4
	end
	if fields.map55 then
		butX=5
		butZ=5
	end
	if fields.map56 then
		butX=5
		butZ=6
	end
	if fields.map57 then
		butX=5
		butZ=7
	end
	if fields.map58 then
		butX=5
		butZ=8
	end
	if fields.map59 then
		butX=5
		butZ=9
	end
	if fields.map60 then
		butX=6
		butZ=0
	end
	if fields.map61 then
		butX=6
		butZ=1
	end
	if fields.map62 then
		butX=6
		butZ=2
	end
	if fields.map63 then
		butX=6
		butZ=3
	end
	if fields.map64 then
		butX=6
		butZ=4
	end
	if fields.map65 then
		butX=6
		butZ=5
	end
	if fields.map66 then
		butX=6
		butZ=6
	end
	if fields.map67 then
		butX=6
		butZ=7
	end
	if fields.map68 then
		butX=6
		butZ=8
	end
	if fields.map69 then
		butX=6
		butZ=9
	end
	if fields.map70 then
		butX=7
		butZ=0
	end
	if fields.map71 then
		butX=7
		butZ=1
	end
	if fields.map72 then
		butX=7
		butZ=2
	end
	if fields.map73 then
		butX=7
		butZ=3
	end
	if fields.map74 then
		butX=7
		butZ=4
	end
	if fields.map75 then
		butX=7
		butZ=5
	end
	if fields.map76 then
		butX=7
		butZ=6
	end
	if fields.map77 then
		butX=7
		butZ=7
	end
	if fields.map78 then
		butX=7
		butZ=8
	end
	if fields.map79 then
		butX=7
		butZ=9
	end
	if fields.map80 then
		butX=8
		butZ=0
	end
	if fields.map81 then
		butX=8
		butZ=1
	end
	if fields.map82 then
		butX=8
		butZ=2
	end
	if fields.map83 then
		butX=8
		butZ=3
	end
	if fields.map84 then
		butX=8
		butZ=4
	end
	if fields.map85 then
		butX=8
		butZ=5
	end
	if fields.map86 then
		butX=8
		butZ=6
	end
	if fields.map87 then
		butX=8
		butZ=7
	end
	if fields.map88 then
		butX=8
		butZ=8
	end
	if fields.map89 then
		butX=8
		butZ=9
	end
	if fields.map90 then
		butX=9
		butZ=0
	end
	if fields.map91 then
		butX=9
		butZ=1
	end
	if fields.map92 then
		butX=9
		butZ=2
	end
	if fields.map93 then
		butX=9
		butZ=3
	end
	if fields.map94 then
		butX=9
		butZ=4
	end
	if fields.map95 then
		butX=9
		butZ=5
	end
	if fields.map96 then
		butX=9
		butZ=6
	end
	if fields.map97 then
		butX=9
		butZ=7
	end
	if fields.map98 then
		butX=9
		butZ=8
	end
	if fields.map99 then
		butX=9
		butZ=9
	end

	if butX ~= -1 then

		if mapitMapState == "t" then
			teleportTargetWuX = pngMinWuX + butX*worldStepWuX + 0.5*worldStepWuX
			teleportTargetWuZ = pngMaxWuZ - butZ*worldStepWuZ - 0.5*worldStepWuZ
			
			local manip = minetest.get_voxel_manip()
			local groundLevel = nil
			local i
			-- This will fail if ground level is below 0 (but this doesn't happen very often)
			for i = 96, -100, -1 do	
				p = {x=teleportTargetWuX, y=i, z=teleportTargetWuZ}
				manip:read_from_map(p, p)
--				player:setpos(p)

				if minetest.get_node(p).name ~= "air" and minetest.get_node(p).name ~= "ignore" then
					groundLevel = i
					break
				end
			end
			if groundLevel ~= nil then
				print("mapit Teleport Successful")
				player:setpos({x=teleportTargetWuX, y=(groundLevel+1), z=teleportTargetWuZ})
			else
				-- minetest failed to load the block within the loop, and never seems to no matter how many loops are executed
				--   (even os.execute("sleep 10") doesn't give it time to do so)
				-- However completing the function and having the player re-activate it seems to trigger the engine to load properly
				-- Don't set player back to departure position, or the block will never be loaded
				minetest.chat_send_player(mapitPlayerName, "mapit: Aaarrrgh Teleport Mistargeted (Please Try Again)", false)

				print("mapit Teleport Failed")

			end
		end
		generateMapStrings()
		minetest.show_formspec(mapitPlayerName, "mapit:maptool", mapitFormspecMouse)
		mapitMapState = "t"
	end

	butX=-1
	butZ=-1


end)






local function getGroundLevel(x,z)
	local low = -100
	local high = 101
	local maxLight = 15
	local noon = 0.5
	for y = high, low, -1 do
		lightLevel = get_node_light({x,y,z}, noon)
		if lightLevel < maxLight then
			break
		end
	end
	return y+1
end








-- PNG Processing
-- pngparse.lua
-- Simple example of parsing the main sections of a PNG file.
--
-- This is mostly just an example.  Not intended to be complete,
-- robust, modular, or well tested.
--
-- (c) 2008 David Manura. Licensed under the same terms as Lua (MIT license).
-- [with some minor editing by David Mckenzie 2014 for use in the minetest mod]


-- Unpack 32-bit unsigned integer (most-significant-byte, MSB, first)
-- from byte string.
local function unpack_msb_uint32(s)
  local a,b,c,d = s:byte(1,#s)
  local num = (((a*256) + b) * 256 + c) * 256 + d
  return num
end

-- Read 32-bit unsigned integer (most-significant-byte, MSB, first) from file.
local function read_msb_uint32(fh)
  return unpack_msb_uint32(fh:read(4))
end

-- Read unsigned byte (integer) from file
local function read_byte(fh)
  return fh:read(1):byte()
end


local function parse_zlib(fh, len)
  local byte1 = read_byte(fh)
  local byte2 = read_byte(fh)

  local compression_method = byte1 % 16
  local compression_info = math.floor(byte1 / 16)

  local fcheck = byte2 % 32
  local fdict = math.floor(byte2 / 32) % 1
  local flevel = math.floor(byte2 / 64)

  -- print("compression_method=", compression_method)
  -- print("compression_info=", compression_info)
  -- print("fcheck=", fcheck)
  -- print("fdict=", fdict)
  -- print("flevel=", flevel)

  fh:read(len - 6)
  -- print("(deflate data not displayed)")

  local checksum = read_msb_uint32(fh)
  -- print("checksum=", checksum)
end

local function parse_IHDR(fh, len)
  assert(len == 13, 'format error')
  local width = read_msb_uint32(fh)
  local height = read_msb_uint32(fh)
  local bit_depth = read_byte(fh)
  local color_type = read_byte(fh)
  local compression_method = read_byte(fh)
  local filter_method = read_byte(fh)
  local interlace_method = read_byte(fh)

  -- print("width=", width)
  -- print("height=", height)
  -- print("bit_depth=", bit_depth)
  -- print("color_type=", color_type)
  -- print("compression_method=", compression_method)
  -- print("filter_method=", filter_method)
  -- print("interlace_method=", interlace_method)

  return compression_method, width, height
end

local function parse_sRGB(fh, len)
  assert(len == 1, 'format error')
  local rendering_intent = read_byte(fh)
  -- print("rendering_intent=", rendering_intent)
end

local function parse_gAMA(fh, len)
  assert(len == 4, 'format error')
  local rendering_intent = read_msb_uint32(fh)
  -- print("rendering_intent=", rendering_intent)
end

local function parse_cHRM(fh, len)
  assert(len == 32, 'format error')

  local white_x = read_msb_uint32(fh)
  local white_y = read_msb_uint32(fh)
  local red_x = read_msb_uint32(fh)
  local red_y = read_msb_uint32(fh)
  local green_x = read_msb_uint32(fh)
  local green_y = read_msb_uint32(fh)
  local blue_x = read_msb_uint32(fh)
  local blue_y = read_msb_uint32(fh)
  -- print('white_x=', white_x)
  -- print('white_y=', white_y)
  -- print('red_x=', red_x)
  -- print('red_y=', red_y)
  -- print('green_x=', green_x)
  -- print('green_y=', green_y)
  -- print('blue_x=', blue_x)
  -- print('blue_y=', blue_y)
end

local function parse_IDAT(fh, len, compression_method)
  if compression_method == 0 then
    -- fh:read(len)
    parse_zlib(fh, len)
  else
    -- print('(unrecognized compression method)')
  end  
end

function parse_png(filename)
  local fh = assert(io.open(filename, 'rb'))
  local keyword
  local text
  local i
  local pngRegionWu
  local borderPx
  local pixPerNodePx
  local pngMinWuX
  local pngMaxWuZ
  local height, width


  -- parse PNG header
  local bytes = fh:read(8)
  local expect = "\137\080\078\071\013\010\026\010"
  if bytes ~= expect then
    minetest.chat_send_player(mapitPlayerName, "mapit: fatal error: not a PNG file" .. filename, false)
    print("mapit: fatal error: not a PNG file" .. filename)
  else
--    minetest.chat_send_player(mapitPlayerName, "mapit: valid PNG file" .. filename, false)
  end


  -- parse chunks
  local compression_method
  while 1 do
    local len = read_msb_uint32(fh)
    local stype = fh:read(4)
    -- print("chunk:", "type=", stype, "len=", len)

    if stype == 'IHDR' then
      compression_method, width, height = parse_IHDR(fh, len)
    elseif stype == 'sRGB' then
      parse_sRGB(fh, len)
    elseif stype == 'gAMA' then
      parse_gAMA(fh, len)
    elseif stype == 'cHRM' then
      parse_cHRM(fh, len)
    elseif stype == 'IDAT' then
      parse_IDAT(fh, len, compression_method)
    elseif stype == 'tEXt' then
      local data = fh:read(len)
      for i = 1, len do
        if data:byte(i)== 0 then
          keyword = data:sub(1, i-1)
          text = data:sub(i+1,len)
          break
        end
      end

--      print ("mapit: tEXt data=" .. data)
--      print ("mapit: tEXt len=" .. len)
--      print ("mapit: tEXt keyword=".. keyword)
--      print ("mapit: tEXt text=" .. text)
      if keyword == "pngRegion" then 
        pngRegionWu = text
      elseif keyword == "pngMinX" then 
        pngMinWuX = tonumber(text)
      elseif keyword == "pngMaxZ" then 
        pngMaxWuZ = tonumber(text)
      elseif keyword == "border" then 
        borderPx = tonumber(text)
      elseif keyword == "pixPerNode" then 
        pixPerNodePx = tonumber(text)
      end

      -- print("data=", len == 0 and "(empty)" or "(not displayed)")
    else
      local data = fh:read(len)
      -- print ("mapit: Unknown data=" .. data)
      -- print("data=", len == 0 and "(empty)" or "(not displayed)")
    end

    local crc = read_msb_uint32(fh)
    -- print("crc=", crc)

    if stype == 'IEND' then
      break
    end
  end
--      print ("mapit: tEXt pngRegionWu=".. pngRegionWu)
--      print ("mapit: tEXt pngMinWuX=" .. pngMinWuX)
--      print ("mapit: tEXt pngMaxWuZ=" .. pngMaxWuZ)
--      print ("mapit: tEXt borderPx=" .. borderPx)
--      print ("mapit: tEXt pixPerNodePx=" .. pixPerNodePx)

  return width, height, pngRegionWu, pngMinWuX, pngMaxWuZ, borderPx, pixPerNodePx
end

if minetest.get_modpath("unified_inventory") then
	inv_mod = "unified_inventory"
	unified_inventory.register_button("mapit", {
		type = "image",
		image = "unified_inventory_mapit.png",
	})
	unified_inventory.register_page("mapit", {
		get_formspec = function(player)
			mapitPlayerName= player:get_player_name()

			-- GET NAMES AND PATHS TO ENSURE CORRECT MAP IS USED
			local worldPath = minetest.get_worldpath()
			local worldName = string.gsub(worldPath, "(.*/)(.*)", "%2")

			local mapFileName = worldName:gsub("%s+", "_").. ".png"
			
			local formspec = "image_button[0.06,0.99;7.92,7.52;"..mapFileName..";uI;click here for map]"
			print ('mapit')
			print (formspec)

			return {formspec=formspec}
		end,
	})
end


