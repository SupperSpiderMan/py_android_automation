#!/usr/bin/env python
# coding=utf-8

import sys
import json
import os
import shutil
import time
from optparse import OptionParser

import regex as re
import requests

global_result = 0
global_action_id = ''


class oem_config:
    def __init__(self, config):
        if 'appName' in config and len(config['appName']) > 0:
            self.name = config['appName']
        else:
            self.name = 'EveryBIM'

        # if 'versionName' in config and len(config['versionName']) > 0:
        #     self.version_name = config['versionName']
        # else:
        #     self.version_name = ''

        if 'serverAddress' in config and len(config['serverAddress']) > 0:
            self.server_address = config['serverAddress']
        else:
            self.server_address = "https://cloud.everybim.net"

        if 'packageId' in config and len(config['packageId']) > 0:
            self.package_id = config['packageId']
        else:
            self.package_id = ''

        if 'logoAddress' in config and len(config['logoAddress']) > 0:
            self.app_logo_address = config['logoAddress']
        else:
            self.app_logo_address = ''

        if 'splashAddress' in config and len(config['splashAddress']) > 0:
            self.splash_logo_address = config['splashAddress']
        else:
            self.splash_logo_address = ''


def main(option):
    global global_result
    config = oem_config(json.loads(option.config))
    try:
        update_ops_status('开始打包')
        clear_env()
        resolve_svg(config.app_logo_address, config.splash_logo_address)
        has_base = check_base_apk()
        if has_base:
            return
        else:
            compile_source(config.name, option.version, config.server_address, config.package_id)

    except Exception as e:
        update_ops_status("编译失败: " + str(e))
        flush_out(e)
    finally:
        # 放弃所有本地修改
        os.system("git checkout .")

    if global_result > 0:
        update_ops_status("编译成功")
        flush_out("打包失败")
        exit(1)
    else:
        flush_out("打包成功")
        exit(0)


def compile_source(name, version_name, server_address, package_id):
    replace_source_configs(name, version_name, server_address)
    replace_source_pics()
    prepare_source_env()
    compile_source_code(name)
    upload_to_server('./apk', package_id)
    return


def clear_env():
    # 清理环境
    # 移除所有build文件夹
    try:
        flush_out('清理编译环境')
        execute('find . -name "build" | xargs rm -rf')
        execute('find . -name ".hprof" | xargs rm -r')
        execute('rm -rf logo.svg')
        execute('rm -rf splash.svg')
        execute('rm -rf logo')
        execute('rm -rf splash')
        execute('rm -rf build_source_log.txt')
        execute('rm -rf apk')
        execute('rm -rf env')
    finally:
        flush_out('清理编译环境完成')


def upload_to_server(file_path, package_id):
    if len(package_id) > 5:
        flush_out('准备上传包管理平台 约3-5分钟')
        update_ops_status('安装包上传(3-5分钟)')
        upload_address = "https://console.ezbim.net/api/files"
        application_address = "https://console.ezbim.net/api/applications"
        if os.path.isdir(file_path):
            for item in os.listdir(file_path):
                file = {'file': open(os.path.join(file_path, item), 'rb')}
                result = requests.post(upload_address, files=file)
                json_result = json.loads(result.text)
                if "file" in json_result.keys():
                    data = {'fileId': json_result['file'],
                            'device': 'android',
                            'forced': 'false',
                            "installPackageId": package_id}
                    result = requests.post(application_address, data=data)
                    json_result = json.loads(result.text)
                    if "_id" in json_result.keys():
                        flush_out(
                            "上传成功 : https://console.ezbim.net/packages?id=" + json_result['_id'])
                    else:
                        flush_out("上传包管理平台失败")
    else:
        flush_out('跳过上传包管理平台')


def compile_source_code(name):
    flush_out('开始全量编译打包 约10-15分钟')
    update_ops_status('全量编译(10-15分钟)')
    cscec_chanel = 'C8BIM'
    if cscec_chanel == name:
        chanel = 'cscec'
    else:
        chanel = 'everybim'
    execute('gradle' + ' assemble' + chanel.capitalize() + 'Release' +
            ' > build_source_log.txt 2>&1')
    flush_out('全量编译打包完成')
    update_ops_status('编译完成等待上传')


def prepare_source_env():
    flush_out('准备编译环境')
    execute('gradle wrapper > env.txt 2>&1')
    flush_out('编译环境准备完成')


def replace_source_pics():
    flush_out('开始替换全量编译LOGO文件')
    root_dir = os.getcwd()
    logo_path = os.path.join(root_dir, "logo")
    resource_path = os.path.join(
        root_dir,
        'app',
        'src',
        'main',
        'res'
    )
    if os.path.isdir(logo_path):
        flush_out('开始替换图标LOGO文件')
        for child in os.listdir(logo_path):
            if os.path.isdir(os.path.join(logo_path, child)):
                for item in os.listdir(os.path.join(logo_path, child)):
                    make_dir(os.path.join(resource_path, child))
                    flush_out('替换 ' + child + " " + item + ' 文件')
                    replace_pic(os.path.join(logo_path, child, item),
                                os.path.join(resource_path, child, item))
        flush_out('替换图标LOGO文件完成')
    else:
        flush_out('跳过图标LOGO文件替换')

    splash_path = os.path.join(root_dir, "splash")
    if os.path.isdir(splash_path):
        flush_out('开始替换启动页LOGO文件')
        for child in os.listdir(splash_path):
            if os.path.isdir(os.path.join(splash_path, child)):
                for item in os.listdir(os.path.join(splash_path, child)):
                    make_dir(os.path.join(resource_path, child))
                    flush_out('替换 ' + child + " " + item + ' 文件')
                    replace_pic(os.path.join(splash_path, child, item),
                                os.path.join(resource_path, child, item))
        flush_out('替换启动页LOGO文件完成')
    else:
        flush_out('跳过启动页LOGO文件替换')

    flush_out('全量编译LOGO文件替换完成')

    if os.path.exists(logo_path):
        shutil.rmtree(logo_path)
    if os.path.exists(splash_path):
        shutil.rmtree(splash_path)


def replace_pic(source, target):
    shutil.copyfile(source, target)


def replace_source_configs(name, version_name, server_address):
    global global_result
    flush_out('开始替换APP配置项完毕')
    version_name_pattern = "(?<=versionName\\s+:\\s+\").*?(?=\")"
    application_name_pattern = "(?<=applicationName\\s*:\\s*\").*?(?=\")"
    server_address_pattern = "(?<=serverAddress\\s*:\\s*\").*?(?=\")"
    root_dir = os.getcwd()
    config_path = os.path.join(root_dir, "app.gradle")
    if not os.path.exists(config_path):
        global_result = 1
        raise RuntimeError('APP配置文件丢失，请添加配置文件')
    config_file = open(config_path, "r+")
    config_txt = config_file.read()
    if len(name) > 0:
        version_name_pattern = re.compile(version_name_pattern)
        if len(version_name_pattern.findall(config_txt)) == 0:
            flush_out('跳过APP版本名称替换')
        else:
            config_txt = version_name_pattern.sub(version_name, config_txt)
            flush_out('完成APP版本名称替换')
    else:
        flush_out('跳过APP版本名称替换')
    if len(version_name) > 0:
        application_name_pattern = re.compile(application_name_pattern)
        if len(application_name_pattern.findall(config_txt)) == 0:
            flush_out('跳过APP名称替换')
        else:
            config_txt = application_name_pattern.sub(name, config_txt)
            flush_out('完成APP名称替换')
    else:
        flush_out('跳过APP名称替换')
    if len(server_address_pattern) > 0:
        server_address_pattern = re.compile(server_address_pattern)
        if len(server_address_pattern.findall(config_txt)) == 0:
            flush_out('跳过APP服务器地址替换')
        else:
            config_txt = server_address_pattern.sub(server_address, config_txt)
            flush_out('完成APP服务器地址替换')
    else:
        flush_out('跳过APP服务器地址替换')

    config_file.seek(0)  # 移动文件指针
    config_file.truncate()  # 同时清除文件内容
    config_file.write(config_txt)  # 将新的配置文件写入
    config_file.close()
    flush_out('替换APP配置项完毕')


def resolve_svg(app_logo_address, splash_logo_address):
    flush_out('开始下载图标文件')
    if len(app_logo_address) > 0:
        flush_out('开始下载APP图标')
        execute('wget ' + app_logo_address + ' -q' + ' -O logo.svg')
        configs = [
            svg_config('logo' + os.sep + 'mipmap-mdpi', 'ic_launcher_logo', '100%'),
            svg_config('logo' + os.sep + 'mipmap-hdpi', 'ic_launcher_logo', '150%'),
            svg_config('logo' + os.sep + 'mipmap-xhdpi', 'ic_launcher_logo', '200%'),
            svg_config('logo' + os.sep + 'mipmap-xxhdpi', 'ic_launcher_logo', '300%'),
            svg_config('logo' + os.sep + 'mipmap-xxxhdpi', 'ic_launcher_logo', '400%')]
        for item in configs:
            svg_resize('logo.svg', item)
        flush_out('APP图标裁剪完成')
    else:
        flush_out('跳过下载APP图标')

    if len(splash_logo_address) > 0:
        flush_out('开始下载启动页图标')
        execute('wget ' + splash_logo_address + ' -q' + ' -O splash.svg')
        configs = [
            svg_config('splash' + os.sep + 'drawable-mdpi', 'ic_launcher_logo', '100%'),
            svg_config('splash' + os.sep + 'drawable-hdpi', 'ic_launcher_logo', '150%'),
            svg_config('splash' + os.sep + 'drawable-xhdpi', 'ic_launcher_logo', '200%'),
            svg_config('splash' + os.sep + 'drawable-xxhdpi', 'ic_launcher_logo', '300%'),
            svg_config('splash' + os.sep + 'drawable-xxxhdpi', 'ic_launcher_logo', '400%')]
        for item in configs:
            svg_resize('splash.svg', item)
        flush_out('启动页图标裁剪完成')
    else:
        flush_out('跳过下载启动页图标')
    flush_out('下载图标文件完毕')


def svg_resize(svg_path, size_config):
    make_dir(size_config['dir'])
    execute("/usr/local/bin/convert -density 160" +
            " -resize " + size_config['size'] +
            " " + svg_path + " " + size_config['dir'] +
            os.sep + size_config['name'] + '.png')


def svg_config(dir_name, name, size):
    return {'size': size, 'dir': dir_name, 'name': name}


def check_base_apk():
    return False


def make_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def execute(command):
    global global_result
    result = os.system(command)
    if result > 0:
        global_result = result
        raise Exception("执行失败: " + command)


def update_ops_status(status):
    global global_action_id
    if global_action_id == "":
        return
    update_url = "https://console.ezbim.net/api/automation/android/actions/" + global_action_id
    params = {"status": status}
    requests.put(update_url, json=params)


def flush_out(args):
    print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()) + " ===> " + str(args))
    sys.stdout.flush()


def parser_config():
    parser = OptionParser()
    parser.add_option("-c", "--config",
                      type="string",
                      metavar="config")
    parser.add_option("-a", "--action",
                      type="string",
                      metavar="action",
                      default="")
    parser.add_option("-v", "--version",
                      type="string",
                      metavar="version")
    (option, _) = parser.parse_args()
    return option


if __name__ == '__main__':
    option = parser_config()
    reload(sys)
    sys.setdefaultencoding('utf8')
    flush_out(option)
    global_action_id = option.action
    main(option)
