import shell from "shelljs";
import * as sh from "shelljs";
import { exec } from "shelljs";
import { exec as run } from "shelljs";
import type { exec as typedExec } from "shelljs";

const shellReq = require("shelljs");
const { exec: execReq } = require("shelljs");

const other = { exec: (cmd: string) => cmd };

export function ping(host: string) {
  shell.exec(`ping -c 1 ${host}`);
  sh.exec("ping -c 1 " + host);
  exec(`ping -c 1 ${host}`);
  run("ping -c 1 " + host);
  shellReq.exec(`ping -c 1 ${host}`);
  execReq("ping -c 1 " + host);
  shell.exec("ls");
  shell.exec(`ls`);
  shell.exec("ping " + "127.0.0.1");
  shell.exec(host);
  other.exec(`ping -c 1 ${host}`);
  typedExec(`ping -c 1 ${host}`);
}
