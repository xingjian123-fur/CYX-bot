import re

from nonebot import on_fullmatch, on_regex
from nonebot.adapters.onebot.v11 import MessageEvent, PrivateMessageEvent
from nonebot.params import Depends, RegexMatched
from nonebot.permission import SUPERUSER

from ..libraries.maimaidx_music_info import *
from ..libraries.maimaidx_player_score import *
from ..libraries.maimaidx_update_plate import *

update_table            = on_fullmatch('更新定数表', permission=SUPERUSER)
update_plate            = on_fullmatch('更新完成表', permission=SUPERUSER)
rating_table            = on_regex(r'([0-9]+\+?)定数表')
rating_table_pfm        = on_regex(r'^([0-9]+\+?)(([apfcp]+|\+)+)?完成表$', re.IGNORECASE)
plate_table_pfm         = on_regex(r'^([真超檄橙暁晓桃櫻樱紫菫堇白雪輝辉舞霸熊華华爽煌星宙祭祝双宴镜])([極极将舞神者]舞?)完成表$')
rise_score              = on_regex(r'^我要在?([0-9]+\+?)?[上加\+]([0-9]+)?分\s?(.+)?')
plate_process           = on_regex(r'^([真超檄橙暁晓桃櫻樱紫菫堇白雪輝辉舞霸熊華华爽煌星宙祭祝双宴镜])([極极将舞神者]舞?)进度\s?(.+)?')
level_process           = on_regex(r'^([0-9]+\+?)\s?([abcdsfxp\+]+)\s?([\u4e00-\u9fa5]+)?\s?进度\s?([0-9]+)?(.+)?', re.IGNORECASE)
level_achievement_list  = on_regex(r'^([0-9]+\.?[0-9]?\+?)\s?分数列表\s?([0-9]+)?\s?(.+)?')


def get_at_qq(message: MessageEvent) -> Optional[int]:
    for item in message.message:
        if isinstance(item, MessageSegment) and item.type == 'at' and item.data['qq'] != 'all':
            return int(item.data['qq'])
    return None


@update_table.handle()
async def _(event: PrivateMessageEvent):
    await update_table.finish(await update_rating_table())
    

@update_plate.handle()
async def _(event: PrivateMessageEvent):
    await update_plate.finish(await update_plate_table())


@rating_table.handle()
async def _(match = RegexMatched()):
    args = match.group(1).strip()
    if args in levelList[:6]:
        await rating_table.finish('只支持查询lv7-15的定数表', reply_message=True)
    elif args in levelList[6:]:
        path = ratingdir / f'{args}.png'
        pic = draw_rating(args, path)
        await rating_table.finish(pic, reply_message=True)
    else:
        await rating_table.finish('无法识别的定数', reply_message=True)


@rating_table_pfm.handle()
async def _(event: MessageEvent, match = RegexMatched()):
    ra = match.group(1)
    plan = match.group(2)
    if ra in levelList[:6]:
        await rating_table_pfm.finish('只支持查询lv7-15的完成表', reply_message=True)
    elif ra in levelList[6:]:
        pic = await draw_rating_table(event.user_id, ra, True if plan and plan.lower() in comboRank else False)
        await rating_table_pfm.finish(pic, reply_message=True)
    else:
        await rating_table_pfm.finish('无法识别的定数', reply_message=True)


@plate_table_pfm.handle()
async def _(event: MessageEvent, match = RegexMatched()):
    ver = match.group(1)
    plan = match.group(2)
    if ver in platecn:
        ver = platecn[ver]
    if ver in ['舞', '霸']:
        await plate_table_pfm.finish('暂不支持查询「舞」系和「霸者」的牌子', reply_message=True)
    if f'{ver}{plan}' == '真将':
        await plate_table_pfm.finish('真系没有真将哦', reply_message=True)
    pic = await draw_plate_table(event.user_id, ver, plan)
    await plate_table_pfm.finish(pic, reply_message=True)


@rise_score.handle()
async def _(event: MessageEvent, match = RegexMatched(), user_id: Optional[int] = Depends(get_at_qq)):
    qqid = user_id or event.user_id
    username = None
    
    rating = match.group(1)
    score = match.group(2)
    
    if rating and rating not in levelList:
        await rise_score.finish('无此等级', reply_message=True)
    elif match.group(3):
        username = match.group(3).strip()
    if username:
        qqid = None

    data = await rise_score_data(qqid, username, rating, score)
    await rise_score.finish(data, reply_message=True)


@plate_process.handle()
async def _(event: MessageEvent, match = RegexMatched(), user_id: Optional[int] = Depends(get_at_qq)):
    qqid = user_id or event.user_id
    ver = match.group(1)
    plan = match.group(2)
    
    if f'{ver}{plan}' == '真将':
        await plate_process.finish('真系没有真将哦', reply_message=True)

    data = await player_plate_data(qqid, '', ver, plan)
    await plate_process.finish(data, reply_message=True)


@level_process.handle()
async def _(event: MessageEvent, match = RegexMatched(), user_id: Optional[int] = Depends(get_at_qq)):
    qqid = user_id or event.user_id
    
    level = match.group(1)
    plan = match.group(2)
    category = match.group(3)
    page = match.group(4)
    username = match.group(5)
    
    if level not in levelList:
        await level_process.finish('无此等级', reply_message=True)
    if plan.lower() not in scoreRank + comboRank + syncRank:
        await level_process.finish('无此评价等级', reply_message=True)
    if levelList.index(level) < 11 or (plan.lower() in scoreRank and scoreRank.index(plan.lower()) < 8):
        await level_process.finish('兄啊，有点志向好不好', reply_message=True)
    if category:
        if category in ['已完成', '未完成', '未开始']:
            _c = {
                '已完成': 'completed',
                '未完成': 'unfinished',
                '未开始': 'notstarted',
                '未游玩': 'notstarted'
            }
            category = _c[category]
        else:
            await level_process.finish(f'无法指定查询「{category}」', reply_message=True)
    else:
        category = 'default'

    data = await level_process_data(qqid, username, level, plan, category, int(page) if page else 1)
    await level_process.finish(data, reply_message=True)


@level_achievement_list.handle()
async def _(event: MessageEvent, match = RegexMatched(), user_id: Optional[int] = Depends(get_at_qq)):
    qqid = user_id or event.user_id

    rating = match.group(1)
    page = match.group(2)
    username = match.group(3)
    
    try:
        if '.' in rating:
            rating = round(float(rating), 1)
        elif rating not in levelList:
            await level_achievement_list.finish('无此等级', reply_message=True)
    except ValueError:
        if rating not in levelList:
            await level_achievement_list.finish('无此等级', reply_message=True)

    data = await level_achievement_list_data(qqid, username, rating, int(page) if page else 1)
    await level_achievement_list.finish(data, reply_message=True)
