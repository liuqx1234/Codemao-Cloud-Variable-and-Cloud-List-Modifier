import bcmcloud
import time,threading,math
# 主程序
msg_list = []
msg_list.append("默认消息，忽略即可$系统")
#消息格式："消息$用户名"

def send_msg(start_id,end_id,json,client_sendMsg):
    global bcmcloud_worker
    max_end_time = time.time()+25#设置与客户端交流的最大时间
    for i in range(start_id,end_id):
        if i%2==1:
            msg = "get_msg_done&"+client_sendMsg[1]+"&"+msg_list[i]
        else:
            msg = "get_msg_done&"+client_sendMsg[1]+"&"+msg_list[i]+" "
        bcmcloud_worker.list_replace("event_ls",json["nth"],msg)
        while True:
            time.sleep(1)
            temp = bcmcloud_worker.list_get("event_ls")
            if temp[json["nth"]-1] == "next":
                break
            if max_end_time<time.time():
                bcmcloud_worker.list_replace("event_ls",json["nth"],"empty")
                return 
    msg = "get_msg_done&"+client_sendMsg[1]+"&get_ok"
    bcmcloud_worker.list_replace("event_ls",json["nth"],msg)
    time.sleep(10)
    #a.view_list("event_ls",json.get("nth"))
    return 

def handle_listEvent(json):
    """
    下面是一个用户请求聊天消息的示例，此聊天室存储请求的云数据是一个列表，用户会找到最前一个空闲的云列表项，来发送下面的信息：

    A: 用户发送: get_msg&2A69818C827B3656&1
       意思是会话 id 为 2A69818C827B3656 的用户请求 get_msg(获取聊天信息的意思) 并且是获取第 1 页的

    B: 返回消息: get_msg_done&2A69818C827B3656&默认消息，忽略即可$系统
       意思为会话 id 为 2A69818C827B3656 的用户收到了 1 条消息，为 get_msg_done(成功获取了一条消息的意思) ，且消息为 默认消息，忽略即可$系统 
       其中 “默认消息，忽略即可” 为那个用户发的文字， “系统”为用户id(通常情况下为训练师编号,只是这条消息比较特殊)

    C: 用户发送: next
       意思是用户已经接收了这条消息，请服务器继续发送下一条消息。接下来会一直执行B步骤和C步骤，如果聊天消息足够的情况下，最多发送10条消息。

    D: 返回消息: get_msg_done&2A69818C827B3656&get_ok
       意思是服务器已经发送完会话 id 为 2A69818C827B3656 的消息了

    E: 用户发送: empty
       意思是客户端已接收完毕，修改该云列表项为空闲状态。接收完毕
    
    注: 此程序有超时功能，如果用户在25秒内没有接收消息，服务器会强制修改该云列表项为空闲状态，并结束此获取评论会话(当前其他的会话和以后的会话不会影响)
    """

    global bcmcloud_worker
    user_method = json.get("value").split("&")
    #a.noview_list("event_ls",json.get("nth"))
    #考虑到目前noview和view函数有bug，因此不建议使用
    if user_method[0] == "get_msg":
        client_sendMsg:str = json.get("value")
        client_sendMsg = client_sendMsg.split("&")
        room_id = client_sendMsg[1]
        page = client_sendMsg[2]
        end_id = int(page)*10
        start_id = end_id-10
        if end_id > len(msg_list):
            end_id = len(msg_list)
        if client_sendMsg[0] == "get_msg":
            kkk = threading.Thread(target=send_msg,args=(start_id,end_id,json,client_sendMsg,))
            kkk.daemon = True
            kkk.start()
    elif user_method[0] == "send_msg":
        client_sendMsg:str = json.get("value")
        client_sendMsg = client_sendMsg.split("&")
        room_id = client_sendMsg[1]
        user_id = client_sendMsg[2]
        message = client_sendMsg[3]
        msg_list.append(message+"$"+str(user_id))
        if len(msg_list)>1000:
            msg_list.pop(0)
        client_msg = "send_msg_done&"+str(room_id)+"&send_ok"
        bcmcloud_worker.list_replace("event_ls",json["nth"],client_msg)

def cloud_work():#每隔10秒修改最大页数
    global bcmcloud_worker
    while not bcmcloud_worker.ready:#等待准备就绪
        time.sleep(1)
    while True:
        temp = math.ceil(len(msg_list)/10)
        bcmcloud_worker.var_upd("max_page",temp)
        time.sleep(10)


if __name__ == "__main__":
    config = \
    {
        "phone_number": "18508106180",
        "password": "Yhy3370955",
        "work": "257509128"
    }
    bcmcloud_worker = bcmcloud.codemao_cloud(config)
    threading.Thread(target=cloud_work).start()

    #绑定列表名称为event_ls的replace(替换)事件，处理函数为handle_listEvent
    bcmcloud_worker.bind("event_ls-replace", handle_listEvent, "list_name")

    bcmcloud_worker.run()
