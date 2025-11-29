import websocket,threading
import json,time,requests,queue
from playwright.sync_api import sync_playwright
"""
sclqx.top
© 2025 liuqx. All rights reserved.
"""
class codemao_cloud:
    def __init__(self,config:dict) -> None:
        """
        跟编程猫云变量通讯
        :param config: 传入编程猫登录手机号（phone_number）、密码（password）、作品（work）来确定作品
        """
        self.bind_dict = {}
        self.varAndList_bind = \
        {
            "vars":{},
            "lists":{}
        }
        self.PHONE_NUMBER = config["phone_number"]
        self.PASSWORD = config["password"]
        self.WORK = config["work"]
        self.SPEED = 1#登录速度
        self.msg = True#关闭后将不会在控制台打印websocket消息
        self.online_users = None#在线人数
        self.cvid_to_name = {}#存放cvid对应的元素名称是什么
        self.name_to_cvid = {}#存放元素名称对应的cvid是什么
        self.name_to_uuid = {}#存放cvid对应的uuid是什么
        self.cloud_lists = {}#云列表字典，存放{名称,内容}
        self.cloud_vars = {}#云变量字典，存放{名称,内容}
        self.ready = False#是否准备就绪
        self.method = "threading"#模式，有队列模式和多线程模式
        self.vars_noview = {}#哪些变量不监听
        self.lists_noview = {}#哪些列表项不监听
        self.socket_id = None
        self.__is_talk = False
        self.event_queue = queue.Queue()

    def run(self) -> None:
        """
        初始化云变量通讯，获取密钥，进入作品并开始监听云变量
        """

        print("请稍后，正在登录编程猫，整个过程大约需要{a}秒...".format(a=20*(1/self.SPEED)))
        with sync_playwright() as p:
            # 启动浏览器
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 打开编程猫页面
            page.goto(f"https://player.codemao.cn/new/we/{self.WORK}")

            # 等待页面加载完成
            page.wait_for_timeout(2000*(1/self.SPEED))

            print("后台打开编程猫作品页面完成，开始登录...")
            print("如果长时间卡在登录并报错，尝试将登录速度调小一点(调小会更慢)")

            # 弹出登录窗口的按钮
            page.click(".CUI-player-cover-sign-in-btn")

            # 登录
            page.wait_for_timeout(2000*(1/self.SPEED))
            page.fill("input[type='text']", self.PHONE_NUMBER)
            page.fill("input[type='password']", self.PASSWORD)
            page.wait_for_timeout(2000*(1/self.SPEED))

            # 立即登录按钮
            page.click(".CUI-button-btn-wrap")
            page.wait_for_timeout(3000*(1/self.SPEED))

            #检查是否登录成功
            self.__check_login_error(page,".CUI-sign-in-dialog-input-error")
            self.__check_login_error(page,".CUI-sign-in-dialog-submit-error")

            # 点击“开始运行”按钮，运行编程猫作品
            page.click(".CUI-player-cover-play-btn")

            # 等待页面加载完成
            page.wait_for_timeout(2000*(1/self.SPEED))

            # 获取 Cookie
            cookies = page.context.cookies()

            # 关闭浏览器
            browser.close()
            print("登录成功！即将开始监听云变量(列表)")

        if self.method == "queue":
            self.queue_run_thr = threading.Thread(target=self.__queue_run)
            self.queue_run_thr.daemon = True
            self.queue_run_thr.start()
        self.__websocket_service(cookies)

    def __queue_run(self):
        while True:
            #[msg_json[0],args_json,j]
            if not self.event_queue.empty():
                this_event = self.event_queue.get()
                work_func = this_event[2]
                thr = threading.Thread(target=work_func,args=(this_event[1],))
                thr.start()
                thr.join()
            time.sleep(0.05)

    def __check_login_error(self,page,item):
        error_divs = page.locator(item)
        error_messages = []

        # 遍历所有错误元素
        for i in range(error_divs.count()):
            error_text = error_divs.nth(i).inner_text().strip()  # 获取每个错误元素的内容
            if error_text:  # 如果内容不为空
                error_messages.append(error_text)

        # 如果有错误信息，报错
        if error_messages:
            raise ValueError("编程猫登录失败："+"\n".join(error_messages))

    def __get_msg(self,string):
        #获取状态码以外的消息
        for i in range(0,len(string)):
            try:
                int(string[i])
            except:
                return string[i:]

        #整个消息就是个状态码
        return ""

    # 使用 websocket-client 发送和接收消息
    def __websocket_service(self,cookies):
        # 构造 Cookie 字符串
        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

        # WebSocket 服务器地址
        ws_url = f"wss://socketcv.codemao.cn:9096/cloudstorage/?session_id={self.WORK}&authorization_type=1&stag=1&EIO=3&transport=websocket"

        def on_message(ws, message):
            self.__is_talk = True
            if self.msg and "3" != message:
                print("收到 WebSocket 消息:", message)
            time.sleep(0.1)
            if "40" == message:
                self.ws.send(f'42["join","{self.WORK}"]')
            
            if len(message)>=3 and message[0] == "4" and message[1] == "2":#事件处理
                msg = self.__get_msg(message)
                msg_json = json.loads(msg)
                if len(msg_json) == 2:
                    work_func = self.bind_dict.get(msg_json[0])
                    args_json = msg_json[1]
                    if args_json == "fail":
                        return 
                    if work_func != None:#确保用户绑定了这个事件
                        #不同消息格式用不同的程序进行格式化
                        if msg_json[0] == "update_vars_done":
                            #格式：["update_vars_done",[{"cvid":"cWQBV9FY","value":"abcd1111111"}]]
                            for i in msg_json[1]:
                                args_json = i
                                try:
                                    args_json = json.loads(i)
                                except:
                                    pass
                                this_name = self.cvid_to_name[args_json.get("cvid")]
                                if self.vars_noview[this_name]:#如果这个事件不接收
                                    return 
                                if self.method == "threading":
                                    for j in work_func:
                                        threading.Thread(target=j,args=(args_json,)).start()
                                elif self.method == "queue":
                                    for j in work_func:
                                        self.event_queue.put([msg_json[0],args_json,j])
                        elif msg_json[0] == "update_lists_done":
                            for k,v in msg_json[1].items():
                                try:
                                    args_json = json.loads(v)
                                except:
                                    pass
                                this_name = self.cvid_to_name[k]
                                if self.lists_noview[this_name] == "*" or \
                                    args_json.get("nth") in self.lists_noview[this_name]:#如果这个事件不接收
                                    return 
                                if self.method == "threading":
                                    for j in work_func:
                                        threading.Thread(target=j,args=(args_json,)).start()
                                elif self.method == "queue":
                                    for j in work_func:
                                        self.event_queue.put([msg_json[0],args_json,j])

                        
                        else:
                            args_json = msg_json[1]
                            try:
                                args_json = json.loads(msg_json[1])
                            except:
                                pass
                            if self.method == "threading":
                                for j in work_func:
                                    threading.Thread(target=j,args=(args_json,)).start()
                            elif self.method == "queue":
                                for j in work_func:
                                    self.event_queue.put([msg_json[0],args_json,j])
                    
                    #下面的代码是处理绑定的是云列表或云变量改变事件的
                    if msg_json[0] == "update_vars_done":
                        #格式：["update_vars_done",[{"cvid":"cWQBV9FY","value":"abcd1111111"}]]
                        for i in msg_json[1]:
                            args_json = i
                            try:
                                args_json = json.loads(i)
                            except:
                                pass
                            this_name = self.cvid_to_name[args_json.get("cvid")]
                            work_func = self.varAndList_bind["vars"].get(this_name)
                            if work_func == None:#用户没有绑定这个事件
                                return 
                            if self.vars_noview[this_name]:#如果这个事件不接收
                                return 
                            if self.method == "threading":
                                for j in work_func:
                                    threading.Thread(target=j,args=(args_json,)).start()
                            elif self.method == "queue":
                                for j in work_func:
                                    self.event_queue.put([msg_json[0],args_json,j])
                    
                    if msg_json[0] == "update_lists_done":
                        #格式：["update_lists_done", {4FhUje87: [{action: "append", value: 3, nth: null}]}]
                        for k,v in msg_json[1].items():
                            try:
                                args_json = json.loads(v)
                            except:
                                pass
                            this_name = self.cvid_to_name[k]
                            for i in v:
                                this_action = i.get("action")
                                work_func = self.varAndList_bind["lists"].get(this_name)
                                nth = i.get("nth")
                                if work_func == None:#用户没有绑定这个事件
                                    return 
                                work_func = work_func.get(this_action)
                                if work_func == None and \
                                    self.varAndList_bind["lists"].get(this_name).get("*") == None:#用户没有绑定这个事件
                                    return 
                                if nth != None and nth in self.lists_noview[this_name]:
                                    #如果这个事件不接收
                                    return 
                                if "*" in self.lists_noview[this_name]:
                                    #如果这个事件不接收
                                    return 
                                if self.method == "threading":
                                    for j in work_func:
                                        threading.Thread(target=j,args=(i,)).start()
                                elif self.method == "queue":
                                    for j in work_func:
                                        self.event_queue.put([msg_json[0],i,j])

        def on_error(ws, error):
            print("云变量连接错误："+str(error))

        def on_close(ws, close_status_code, close_msg):
            print(f"编程猫云变量(列表)连接已关闭，关闭代码：{close_status_code}，关闭消息：{close_msg}")
            if not self.__is_talk:
                print("\n检测到此程序和编程猫云变量(列表)没有任何通讯")
                print("可能是因为当前作品id为不存在的作品或者您的作品没有用到云变量")
                print("还有可能是因为您设置的登录速度太快了，尝试将登录速度调小一点(调小会更慢)")

        def on_open(ws):

            self.heartbeat_thr = threading.Thread(target=self.__heartbeat)
            self.heartbeat_thr.daemon = True
            self.heartbeat_thr.start()#心跳，避免连接被断开
            self.bind("connect_done",self.__get_vars)
            self.bind("online_users_change",self.__upd_online_users)
            self.bind("list_variables_done",self.__set_listAndVars)
            self.bind("update_vars_done",self.__upd_var)
            self.bind("update_lists_done",self.__upd_list)
            print("已连接到编程猫云变量(列表)服务器")

        # 创建 WebSocket 连接
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            header={
                "Cookie": cookie_str  # 附加 Cookie
            }
        )
        self.ws.on_open = on_open

        # 保持连接
        self.ws.run_forever()

    def __heartbeat(self):
        while True:
            time.sleep(30)
            self.ws.send("2")

    def bind(self,name:str,func,bind_type:str = "websocket") -> None:
        """
        绑定一个事件
        :param name: 事件名称
        :param func: 事件处理函数
        :param bind_type: 如果设置为字符串“list_name”或“var_name”则参数name指的是云列表或云变量名称改变事件，如果设置为\
        “websocket_name”则参数name指的是websocket消息事件，如果不写这个参数，则默认参数为websocket消息事件\
        建议普通人使用云列表或云变量名称改变事件
        """
        if bind_type == "websocket":
            if self.bind_dict.get(name) == None:
                self.bind_dict[name]=[func]
            else:
                self.bind_dict[name].append(func)
        elif bind_type == "list_name":
            split_name = name.split("-")
            if self.varAndList_bind["lists"].get(split_name[0]) == None:
                self.varAndList_bind["lists"][split_name[0]] = {}
            if self.varAndList_bind["lists"][split_name[0]].get(split_name[1]) == None:
                self.varAndList_bind["lists"][split_name[0]][split_name[1]] = []
            if len(split_name) == 2:
                self.varAndList_bind["lists"][split_name[0]][split_name[1]].append(func)
            else:
                self.varAndList_bind["lists"][split_name[0]]["*"].append(func)
        
        elif bind_type == "var_name":
            if self.varAndList_bind["vars"].get(name) == None:
                self.varAndList_bind["vars"][name] = []
            self.varAndList_bind["vars"][name].append(func)

    def __get_vars(self,args):
        self.socket_id = args.get("socket_id")
        self.ws.send('42["list_variables",{}]')

    def __upd_online_users(self,args):
        self.online_users = args.get("total")

    def __set_listAndVars(self,args):#设置最初的变量和列表
        print("正在请求您的作品信息...")
        work_info = requests.get(f"https://api-creation.codemao.cn/kitten/r2/work/player/load/{self.WORK}")
        work_info = json.loads(work_info.text)
        work_info = work_info.get("source_urls")
        work_info = work_info[0]#获取到源代码链接
        work_code = requests.get(work_info)
        print("已请求到您的作品信息，开始解析您作品的源代码，获取云变量id(没开源的作品也行)")
        print("解析可能会耗费一些时间和空间，具体取决于您的作品大小...")
        work_code = json.loads(work_code.text)
        cloud_variables = work_code["cloud_variables"]
        for k,v in cloud_variables.items():
            self.name_to_uuid[v.get("name")] = v.get("id")
        print("解析完成，启动完成")

        for i in args:
            this_cvid = i.get("cvid")
            this_name = i.get("name")
            this_value = i.get("value")#这个变量类型int、string、list都有可能
            this_type = i.get("type")#type==1时，为变量；type==2时，为列表

            self.cvid_to_name[this_cvid] = this_name
            self.name_to_cvid[this_name] = this_cvid
            if this_type == 1:
                self.cloud_vars[this_name] = this_value
                self.vars_noview[this_name] = False
                if self.varAndList_bind["vars"].get(this_name) == None:
                    self.varAndList_bind["vars"][this_name] = []
            elif this_type == 2:
                self.cloud_lists[this_name] = this_value
                self.lists_noview[this_name] = set()
                if self.varAndList_bind["lists"].get(this_name) == None:
                    self.varAndList_bind["lists"][this_name] = {}
        self.ready = True

    def __upd_var(self,args):#格式：{'cvid': 'cWQBV9FY', 'value': 'wsds1'}
        cvid = args.get("cvid")
        value = args.get("value")
        name = self.cvid_to_name.get(cvid)
        self.cloud_vars[name] = value

    def __upd_list(self,args):#格式：{'4FhUje87': [{'action': 'append', 'value': 1, 'nth': None}]}
        for k,v in args.items():
            name = self.cvid_to_name.get(k)
            work = v[0]
            action = work.get("action")
            value = work.get("value")
            nth = work.get("nth")
            if nth:
                nth-=1#源码编辑器里的下标是从1开始的
            if action == "append":#列表添加操作
                self.cloud_lists[name].append(value)
            elif action == "replace":#列表替换操作
                if len(self.cloud_lists[name])<nth+1:#如果替换的项不存在(比如列表只有2项却要替换第3项)
                    self.cloud_lists[name].append(value)#直接末尾追加
                else:
                    self.cloud_lists[name][nth] = value
            elif action == "delete":#列表删除项操作
                if len(self.cloud_lists[name])<nth+1:#如果删除的项不存在(比如列表只有2项却要删除第3项)
                    continue
                else:
                    self.cloud_lists[name].pop(nth)
            elif action == "insert":
                if len(self.cloud_lists[name])<nth+1:#如果插入目标的项不存在(比如列表只有2项却要插入第3项的的位置)
                    self.cloud_lists[name].append(value)#直接在末尾插入
                else:
                    self.cloud_lists[name].insert(nth,value)

    def var_get(self,name:str) -> int|str:
        """
        获取某个云变量的值
        :param name: 云变量名称
        """
        return self.cloud_vars[name]
    
    def list_get(self,name:str) -> list:
        """
        获取某个云列表的所有元素
        :param name: 云列表名称
        """
        return self.cloud_lists[name]
    
    def close(self) -> None:
        """
        关闭编程猫云变量(列表)连接
        """
        self.ws.close()
    
    def var_upd(self,var_name:str,value:int|str) -> None:
        """
        修改云变量值,注意两次相同变量的修改需要间隔至少0.5秒
        :param var_name: 云变量名称
        :param value: 要修改的值,由于kitten自身有bug,不能设置修改的值为列表
        """
        self.cloud_vars[var_name] = value
        this_cvid = str(self.name_to_cvid[var_name])
        if type(value) == int:
            self.ws.send('42["update_vars",[{"cvid": "'+this_cvid+
                        '","value": '+str(value)+',"action": "set","param_type": "number"}]]')
        if type(value) == str:
            self.ws.send('42["update_vars",[{"cvid": "'+this_cvid+
                        '","value": "'+str(value)+'","action": "set","param_type": "string"}]]')

    def list_append(self,list_name:str,value:str|int) -> None:
        """
        云列表末尾追加
        :param list_name: 云列表名称
        :param value: 要修改的值
        """
        self.cloud_lists[list_name].append(value)
        if type(value) == int:
            self.ws.send('42["update_lists",{"'+self.name_to_cvid[list_name]+'":[{"id":"'+
                         self.name_to_uuid[list_name]+'","action":"append","value":'+str(value)+
                         ',"cvid":"'+self.name_to_cvid[list_name]+'"}]}]')
        if type(value) == str:
            self.ws.send('42["update_lists",{"'+self.name_to_cvid[list_name]+'":[{"id":"'+
                         self.name_to_uuid[list_name]+'","action":"append","value":"'+str(value)+
                         '","cvid":"'+self.name_to_cvid[list_name]+'"}]}]')

    def list_replace(self,list_name:str,replace_index:int,value:str|int) -> None:
        """
        云列表替换，注意下标是从1开始的,注意两次相同列表项的修改需要间隔至少0.5秒
        :param list_name: 云列表名称
        :param replace_index: 要替换的值的下标
        :param value: 要修改的值
        """
        self.cloud_lists[list_name][replace_index-1] = value
        if type(value) == int:
            self.ws.send('42["update_lists",{"'+self.name_to_cvid[list_name]+'":[{"id":"'+
                         self.name_to_uuid[list_name]+'","action":"replace","value":'+
                         value+',"nth":'+str(replace_index)+',"cvid":"'+self.name_to_cvid[list_name]+'"}]}]')
        if type(value) == str:
            self.ws.send('42["update_lists",{"'+self.name_to_cvid[list_name]+'":[{"id":"'+
                         self.name_to_uuid[list_name]+'","action":"replace","value":"'+
                         value+'","nth":'+str(replace_index)+',"cvid":"'+self.name_to_cvid[list_name]+'"}]}]')
            
    def list_del(self,list_name:str,del_index:int) -> None:
        """
        云列表删除项，注意下标是从1开始的
        :param list_name: 云列表名称
        :param del_index: 要删除的值的下标
        :param value: 要修改的值
        """
        self.cloud_lists[list_name].pop(del_index-1)
        self.ws.send('42["update_lists",{"'+self.name_to_cvid[list_name]+'":[{"id":"'+
                        self.name_to_uuid[list_name]+'","action":"delete","nth":'+
                        str(del_index)+',"cvid":"'+self.name_to_cvid[list_name]+'"}]}]')
        
    def list_insert(self,list_name:str,insert_index:int,value:str|int) -> None:
        """
        云列表插入项,注意下标是从1开始的
        :param list_name: 云列表名称
        :param insert_index: 插入下标
        :param value: 要修改的值
        """
        self.cloud_lists[list_name].insert(insert_index,value)
        if type(value) == int:
            self.ws.send('42["update_lists",{"'+self.name_to_cvid[list_name]+'":[{"id":"'+
                         self.name_to_uuid[list_name]+'","action":"insert","value":'+str(value)+
                         ',"cvid":"'+self.name_to_cvid[list_name]+'","nth":'+str(insert_index)+'}]}]')
        if type(value) == str:
            self.ws.send('42["update_lists",{"'+self.name_to_cvid[list_name]+'":[{"id":"'+
                         self.name_to_uuid[list_name]+'","action":"insert","value":"'+str(value)+
                         '","cvid":"'+self.name_to_cvid[list_name]+'","nth":'+str(insert_index)+'}]}]')
            
    def list_len(self,list_name:str) -> int:
        """
        返回云列表项数
        :param list_name: 云列表名称
        """
        return len(self.cloud_lists[list_name])
    
    def send_message(self,msg) -> None:
        """
        自行发送WebSocket消息
        不建议使用这种方法
        :param msg: 要发送的消息
        """
        self.ws.send(msg)

    def noview_list(self,name:str,nth:int|str) -> None:
        """
        不再接收一个列表某项的改动事件消息（如果期间那一项有改动，会正常改动，但不会被您绑定的函数处理）。
        如果需要一个列表整个事件都不处理，nth变量请设置为字符串“*”
        这个功能通常是需要客户端和服务器不止一条信息交流的时候。
        :param name: 列表名称
        :param nth: 不处理第几项
        """
        self.lists_noview[name].add(nth)

    def view_list(self,name:str,nth:int) -> None:
        """
        开始接收一个列表某项的改动事件消息，这个功能通常配合noview_list()函数使用。
        :param name: 列表名称
        :param nth: 开始处理第几项
        """
        self.lists_noview[name].remove(nth)

    def noview_var(self,name:str) -> None:
        """
        不再接收一个变量的改动事件消息（如果期间那个变量有改动，会正常改动，但不会被您绑定的函数处理）。
        这个功能通常是需要客户端和服务器不止一条信息交流的时候。
        :param name: 变量名称
        """
        self.vars_noview[name] = True

    def view_var(self,name:str) -> None:
        """
        开始接收一个变量的改动事件消息，这个功能通常配合noview_var()函数使用。
        :param name: 变量名称
        """
        self.vars_noview[name] = False


    
def version():
    print("编程猫KITTEN云通讯")
    print("版本1.0.0")
    print("© 2025 liuqx. All rights reserved.")
    print("最后一次修改为2025/7/22")
    print("个人博客：sclqx.top")
    return "1.0.0"